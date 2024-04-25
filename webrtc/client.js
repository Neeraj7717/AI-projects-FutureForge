var pc,dc = null;

let servers = [
    "stun:stun.relay.metered.ca:80"
//     "stun:stun1.l.google.com:19302",
//     "stun:stun2.l.google.com:19302",
//     "stun:stun3.l.google.com:19302",
//     "stun:stun4.l.google.com:19302",
];
function negotiate() {
    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('audio', { direction: 'recvonly' });
    return pc.createOffer().then((offer) => {
        return pc.setLocalDescription(offer);
    }).then(() => {
        // wait for ICE gathering to complete
        return new Promise((resolve) => {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                const checkState = () => {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                };
                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(() => {
        var offer = pc.localDescription;
        var sesId=document.getElementById("sessionId");
        var srcId=document.getElementById("sourceId");
        return fetch('/offer', {
            body: JSON.stringify({
                sessionId: sesId.value,
                sourceId: srcId.value,
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then((response) => {
        return response.json();
    }).then((answer) => {    
       return pc.setRemoteDescription(answer);
        
       // dc.send("ping")


        // dc.addEventListener(onmessage,evt=>{
        //     console.log(evt.data)
        //     })


    }).catch((e) => {
        alert(e);
    });
}

function start() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    if (document.getElementById('use-stun').checked) {
        config.iceServers = [{ urls: servers }];
    }

    pc = new RTCPeerConnection(config);

    // connect audio / video
    pc.addEventListener('track', (evt) => {
        console.log(evt.data)
        if (evt.track.kind == 'video') {
            document.getElementById('video').srcObject = evt.streams[0];
        } else {
            document.getElementById('audio').srcObject = evt.streams[0];
        }
    });
    
//     dc = pc.createDataChannel('chat')
//     dc.onmessage= handleReceiveMessage;
//     // dc.addEventListener(onmessage,evt=>{
//     //     console.log(evt.data)
//     //     })
    document.getElementById('start').style.display = 'none';
    negotiate();
    document.getElementById('stop').style.display = 'inline-block';
}

function stop() {
    document.getElementById('stop').style.display = 'none';

    // close peer connection
    setTimeout(() => {
        pc.close();
    }, 500);
}


// function handleReceiveMessage(event) {
//     console.log(event.data)
//     img = document.getElementById('img')
//     blob = new Blob([event.data])
//     url = URL.createObjectURL(blob)
//     img.src = url
//   }
  