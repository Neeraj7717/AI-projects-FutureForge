import argparse
import asyncio
import base64
import io
import json
import logging
import os
import platform
import ssl
import time
import zlib
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender
import cv2
from kafka import KafkaConsumer
from aiohttp_cors import CorsViewMixin, setup , ResourceOptions
import av
import numpy as np

ROOT = os.path.dirname(__file__)


relay = None
webcam = None
from Config import settings

config=settings.Settings()


def channel_log(channel, t, message):
    print("channel(%s) %s %s" % (channel.label, t, message))


def channel_send(channel, message):
    channel_log(channel, ">", message)
    channel.send(message)

def current_stamp():
    global time_start

    if time_start is None:
        time_start = time.time()
        return 0
    else:
        return int((time.time() - time_start) * 1000000)

def create_local_tracks(play_from, decode):
    global relay, webcam

    if play_from:
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video
    else:
        options = {"framerate": "30", "video_size": "640x480"}
        if relay is None:
            if platform.system() == "Darwin":
                webcam = MediaPlayer(
                    "default:none", format="avfoundation", options=options
                )
            elif platform.system() == "Windows":
                webcam = MediaPlayer(
                    "video=Integrated Camera", format="dshow", options=options
                )
            else:
                webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
            relay = MediaRelay()
        return None, relay.subscribe(webcam.video)
    

def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )

async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


class KafkaImageStreamTrack(VideoStreamTrack):
    def __init__(self,consumer):
        self.consumer=consumer
        super().__init__()
    async def recv(self):
        # Consume messages from Kafka
        for message in self.consumer:
            # Convert Kafka message to image
             
            msg = message.value.decode('utf-8')
            dictionary_data = json.loads(msg)
            image = dictionary_data["image_byte"]
                                   
            image_bytes = base64.b64decode(image)
            decompressed_frame = zlib.decompress(image_bytes)
            file = cv2.imdecode(np.frombuffer(decompressed_frame, np.uint8), cv2.IMREAD_COLOR)

            pts, time_base = await self.next_timestamp()
            frame = av.VideoFrame.from_ndarray(file, format='rgb24')
            frame.pts = pts
            frame.time_base = time_base
            await asyncio.sleep(0)
            return frame

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    kafka_topic=params["sessionId"]
    kafka_topic1=params["sourceId"]
    feature = params.get("feature")
    
    if feature == "via":
        consumer = KafkaConsumer(config.video_details_kafka_topic+kafka_topic, bootstrap_servers=config.kafka_url, auto_offset_reset='latest', api_version=(2, 5, 0),group_id=config.video_details_kafka_topic+kafka_topic)
    else:
        consumer = KafkaConsumer("webrtc"+kafka_topic1, bootstrap_servers=config.kafka_url, auto_offset_reset='latest', api_version=(2, 5, 0),group_id="webrtc"+kafka_topic)
        
        
    pc = RTCPeerConnection()
    pcs.add(pc)
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)
    video_track = KafkaImageStreamTrack(consumer=consumer)

    try:
        pc.addTrack(video_track)
    except Exception as e:
        print(e)
        pass
        
    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )

pcs = set()

async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam demo")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--play-from", help="Read the media from a file and sent it.")
    parser.add_argument(
        "--play-without-decoding",
        help=(
            "Read the media without decoding it (experimental). "
            "For now it only works with an MPEGTS container with only H.264 video."
        ),
        action="store_true",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8061)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument(
        "--audio-codec", help="Force a specific audio codec (e.g. audio/opus)"
    )
    parser.add_argument(
        "--video-codec", help="Force a specific video codec (e.g. video/H264)"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    # app = web.Application()
    app = web.Application()  
    app.router.add_post("/offer", offer)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    cors = setup(app, defaults={"*": ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    for route in list(app.router.routes()):
        cors.add(route)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
