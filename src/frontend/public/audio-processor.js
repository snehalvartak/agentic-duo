class AudioProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    
    if (input.length > 0) {
      const channelData = input[0];
      
      // Convert Float32 to Int16 PCM
      const int16Array = new Int16Array(channelData.length);
      for (let i = 0; i < channelData.length; i++) {
        const s = Math.max(-1, Math.min(1, channelData[i]));
        int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      
      this.port.postMessage(int16Array.buffer, [int16Array.buffer]);
    }
    
    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);

