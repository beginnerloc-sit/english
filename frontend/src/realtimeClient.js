// WebRTC client for the OpenAI Realtime API. The browser never sees the real
// API key — it gets an ephemeral client secret from our backend
// (/session/realtime-token) and connects directly to OpenAI for audio.
//
// Per the current voice-agents docs, the browser POSTs its SDP offer to
// /v1/realtime/calls using the ephemeral secret as a bearer token; session
// config (model, instructions, turn-detection, voice) is baked into the secret
// server-side. OpenAI also ships an @openai/agents/realtime SDK that wraps this
// flow — adopt it if you want tool-calls/handoffs without managing SDP by hand.
// Realtime endpoints/params change often; verify against the docs at build time.

export async function connectRealtime({ clientSecret, model, onRemoteTrack, onEvent }) {
  const pc = new RTCPeerConnection();

  // Remote audio (the AI's voice).
  pc.ontrack = (e) => onRemoteTrack?.(e.streams[0]);

  // Microphone in.
  const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
  const micTrack = mic.getAudioTracks()[0];
  pc.addTrack(micTrack, mic);

  // Data channel for events (transcripts, recasts, etc.).
  const dc = pc.createDataChannel("oai-events");
  dc.onmessage = (e) => {
    try {
      onEvent?.(JSON.parse(e.data));
    } catch {}
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const resp = await fetch(`https://api.openai.com/v1/realtime/calls?model=${model}`, {
    method: "POST",
    body: offer.sdp,
    headers: {
      Authorization: `Bearer ${clientSecret}`,
      "Content-Type": "application/sdp",
    },
  });
  const answer = { type: "answer", sdp: await resp.text() };
  await pc.setRemoteDescription(answer);

  // Push-to-talk: start muted, caller toggles micTrack.enabled.
  micTrack.enabled = false;

  const send = (event) => {
    const payload = JSON.stringify(event);
    if (dc.readyState === "open") dc.send(payload);
    else dc.addEventListener("open", () => dc.send(payload), { once: true });
  };

  return {
    pc,
    dc,
    send,
    setMicEnabled: (on) => {
      micTrack.enabled = on;
    },
    // Patch the live session (e.g. new instructions when the learner switches
    // scaffold rung) without reconnecting. Queues until the channel is open.
    update: (sessionPatch) => send({ type: "session.update", session: sessionPatch }),
    close: () => {
      micTrack.stop();
      dc.close();
      pc.close();
    },
  };
}
