import base64
import subprocess
import numpy as np
import requests
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    RTCConfiguration,
    RTCIceServer
)
import asyncio
import cv2
from ultralytics import YOLO
from kafka import KafkaConsumer
import json

pcs = set()
from config import settings

config=settings.Settings()

topic_name = config.video_details_kafka_topic
consumer = KafkaConsumer(topic_name, bootstrap_servers=config.kafka_url, auto_offset_reset='latest')

SIGNALING_SERVER_URL = config.signaling_server_url
ID = "answerer01"

# model = YOLO("bestVIA.pt", "v8")

def encode_frame_as_h264(frame):
    # Convert frame to H.264 using FFmpeg
    command = ['ffmpeg', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo', '-s', f"{frame.shape[1]}x{frame.shape[0]}", '-pix_fmt', 'bgr24', '-i', '-', '-c:v', 'libx264', '-preset', 'ultrafast', '-f', 'h264', '-']
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate(input=frame.tobytes())

    return stdout
 
async def main():
    peer_connection = RTCPeerConnection()

    async def send_pings(channel):
        for message in consumer:
            msg = message.value.decode('utf-8')
            dictionary_data = json.loads(msg)
            image = dictionary_data["image_byte"]
            image_bytes = base64.b64decode(image)
            channel.send(image_bytes)
            await asyncio.sleep(1)

    @peer_connection.on("datachannel")
    async def on_datachannel(channel):
        await send_pings(channel=channel)
        @channel.on("message")
        async def on_message(message):
            if isinstance(message, str) and message.startswith("ping"):
                channel.send("pong" + message[4:])

    @peer_connection.on("connectionstatechange")
    async def on_connectionstatechange():
        if peer_connection.connectionState == "failed":
            await peer_connection.close()
            pcs.discard(peer_connection)
            # await peer_connection.close()
            # pcs.discard(peer_connection)
    
    resp = requests.get(SIGNALING_SERVER_URL + "/get_offer")

    if resp.status_code == 200:
        data = resp.json()
        if data["type"] == "offer":
            rd = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
            await peer_connection.setRemoteDescription(rd)
            await peer_connection.setLocalDescription(await peer_connection.createAnswer())
            message = {"sessionId": data["sessionId"], "type": peer_connection.localDescription.type, "sdp": peer_connection.localDescription.sdp}
            r = requests.post(SIGNALING_SERVER_URL + '/answer', json=message)

asyncio.run(main())