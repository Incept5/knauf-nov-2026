// Posts mono Float32 PCM frames of ~100 ms to the main thread.
// Copied from biling-mlx (~/dev/mlx-whisper/app/src/biling/web/pcm-worklet.js), channel tag removed.
// The AudioContext runs at 16 kHz, so the browser does the resampling.
class PCMWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(0);
    this.targetFrames = 1600;
  }
  process(inputs) {
    const ch0 = inputs[0] && inputs[0][0];
    if (!ch0) return true;
    const merged = new Float32Array(this.buffer.length + ch0.length);
    merged.set(this.buffer, 0);
    merged.set(ch0, this.buffer.length);
    this.buffer = merged;
    while (this.buffer.length >= this.targetFrames) {
      const slice = this.buffer.slice(0, this.targetFrames);
      this.port.postMessage(slice, [slice.buffer]);
      this.buffer = this.buffer.slice(this.targetFrames);
    }
    return true;
  }
}
registerProcessor("pcm-worklet", PCMWorklet);
