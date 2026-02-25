/**
 * PcmProcessor — AudioWorkletProcessor
 *
 * Captures microphone audio, downsamples from the AudioContext's native
 * sample rate to 16 kHz mono, converts Float32 → Int16 PCM, and posts
 * the buffer to the main thread for WebSocket transmission.
 */
class PcmProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._buffer = [];
        // We accumulate samples and flush every ~100 ms (1600 samples @ 16 kHz)
        this._flushSize = 1600;
    }

    /**
     * Downsample from `srcRate` to `targetRate` by simple nearest-neighbour
     * decimation.  Good enough for voice at 16 kHz.
     */
    _downsample(float32, srcRate, targetRate) {
        if (srcRate === targetRate) return float32;

        const ratio = srcRate / targetRate;
        const len = Math.floor(float32.length / ratio);
        const out = new Float32Array(len);
        for (let i = 0; i < len; i++) {
            out[i] = float32[Math.floor(i * ratio)];
        }
        return out;
    }

    /**
     * Convert a Float32Array (range -1..1) to an Int16Array (range -32768..32767).
     */
    _floatToInt16(float32) {
        const int16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
            const s = Math.max(-1, Math.min(1, float32[i]));
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return int16;
    }

    process(inputs) {
        const input = inputs[0];
        if (!input || input.length === 0) return true;

        // Take only the first channel (mono)
        const channelData = input[0];
        if (!channelData || channelData.length === 0) return true;

        // Downsample to 16 kHz
        const downsampled = this._downsample(channelData, sampleRate, 16000);

        // Accumulate
        for (let i = 0; i < downsampled.length; i++) {
            this._buffer.push(downsampled[i]);
        }

        // Flush when we have enough samples (~100 ms)
        if (this._buffer.length >= this._flushSize) {
            const float32 = new Float32Array(this._buffer);
            this._buffer = [];

            const int16 = this._floatToInt16(float32);

            // Transfer the underlying ArrayBuffer to the main thread
            this.port.postMessage(
                { type: "pcm", buffer: int16.buffer },
                [int16.buffer]
            );
        }

        return true;
    }
}

registerProcessor("pcm-processor", PcmProcessor);
