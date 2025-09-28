import { ref, shallowRef } from 'vue';

// --- Configuration ---
// 在实际应用中，这些应该来自配置文件或环境变量
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const stripTrailingSlash = (value) => (value.endsWith('/') ? value.slice(0, -1) : value);
const normalizePathSegment = (value, fallback) => {
  const raw = (value ?? fallback).trim();
  return raw.replace(/^\/+/, '').replace(/\/+$/, '');
};

const wsBaseOrigin = stripTrailingSlash(
  import.meta.env.VITE_WS_BASE_URL?.trim() || `${wsProtocol}//${window.location.host}`,
);
const wsInputPath = `/${normalizePathSegment(import.meta.env.VITE_WS_INPUT_PATH, 'ws/input')}`;
const wsOutputBasePath = `/${normalizePathSegment(import.meta.env.VITE_WS_OUTPUT_PATH, 'ws/output')}`;
const wsInputUrl = `${wsBaseOrigin}${wsInputPath}`;
const buildOutputWsUrl = (taskId) => `${wsBaseOrigin}${wsOutputBasePath}/${taskId}`;

// --- Reactive State ---
const taskId = ref(null);
const isConnectedInput = ref(false);
const isConnectedOutput = ref(false);
const isProcessing = ref(false); // 用于表示从发送完成到收到结果的过程
const uploadCompleteConfirmed = ref(false); // 确认 upload_complete 已被后端处理
const processingError = ref(null); // 存储处理过程中或连接中的错误信息
const receivedText = ref(''); // 存储接收到的 AI 文本结果
// Audio related state
const audioChunks = shallowRef([]); // Store received audio binary chunks
const expectedAudioChunks = ref(0);
const receivedAudioChunkCount = ref(0);
const lastReceivedAudioChunkId = ref(-1); // Track the ID for the next expected binary chunk
const receivedAudioUrl = ref(null); // URL for the final reassembled audio

// Recording specific state
const isRecording = ref(false);
const recorder = shallowRef(null);
const recordedAudioChunks = shallowRef([]); // Store Blob chunks from MediaRecorder
const recordingError = ref(null); // Store errors related to recording process

// 使用 shallowRef 以避免深度响应性带来的性能问题，因为 WebSocket 实例不应是深度响应式的
const inputWs = shallowRef(null);
const outputWs = shallowRef(null);

// --- WebSocket Logic ---

// Helper to reset all states, especially before a new task
const resetState = () => {
    taskId.value = null;
    isConnectedInput.value = false;
    isConnectedOutput.value = false;
    isProcessing.value = false;
    uploadCompleteConfirmed.value = false;
    processingError.value = null;
    receivedText.value = '';
    audioChunks.value = [];
    expectedAudioChunks.value = 0;
    receivedAudioChunkCount.value = 0;
    lastReceivedAudioChunkId.value = -1;
    if (receivedAudioUrl.value) {
        URL.revokeObjectURL(receivedAudioUrl.value); // Clean up previous blob URL
    }
    receivedAudioUrl.value = null;
    // Reset recording state as well
    isRecording.value = false;
    if (recorder.value && recorder.value.state !== 'inactive') {
        recorder.value.stop();
    }
    recorder.value = null;
    recordedAudioChunks.value = [];
    recordingError.value = null;
};

export function useApi() {

  // --- Input WebSocket Handling ---

  const connectInput = () => {
    // Return a Promise that resolves with the taskId or rejects on error
    return new Promise((resolve, reject) => {
      console.log('Attempting to connect to input WebSocket:', wsInputUrl);
      if (inputWs.value && inputWs.value.readyState === WebSocket.OPEN) {
        console.log('Input WebSocket already open.');
        // If already open and we have a task ID, resolve immediately
        if (taskId.value) {
          resolve(taskId.value);
        } else {
          // If open but no task ID (edge case?), wait for it
          const waitForId = setInterval(() => {
              if (taskId.value) {
                  clearInterval(waitForId);
                  resolve(taskId.value);
              }
              // Add a timeout mechanism here if needed
          }, 100);
        }
        return;
      }

      resetState(); // Reset all states before new connection attempt

      inputWs.value = new WebSocket(wsInputUrl);

      inputWs.value.onopen = () => {
        console.log('Input WebSocket connected.');
        isConnectedInput.value = true;
        processingError.value = null;
        // Don't resolve yet, wait for task_id
      };

      inputWs.value.onmessage = (event) => {
        console.log('Input WebSocket message received:', event.data);
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'system' && message.action === 'task_id_assigned' && message.task_id) {
            taskId.value = message.task_id;
            console.log('Task ID assigned:', taskId.value);
            resolve(taskId.value); // Resolve the Promise with the task ID
            // Automatically connect to output WS once task ID is received
            if (taskId.value) {
               connectOutput(taskId.value);
            }
          } else if (message.type === 'system' && message.action === 'upload_processed' && message.status === 'queued') {
            console.log('Upload processed and queued by backend. Task ID:', message.task_id);
            uploadCompleteConfirmed.value = true;
            isProcessing.value = true; // Indicate that backend processing has started
            // Input stage is complete, disconnect input WebSocket
            disconnectInput();
          }
        } catch (e) {
          // Handle non-JSON messages (confirmations, errors)
          if (event.data === 'File chunk received') {
              console.log('Backend confirmed chunk reception.');
          } else if (event.data.startsWith('Chunk ID mismatch')) {
              console.error('Input WebSocket error:', event.data);
              processingError.value = event.data;
              disconnectInput(); // Disconnect on chunk error
              reject(new Error(event.data)); // Reject promise on critical error
          } else {
              console.warn('Received non-standard text message on input WebSocket:', event.data);
          }
        }
      };

      inputWs.value.onerror = (event) => {
        console.error('Input WebSocket error:', event);
        const errorMsg = '无法连接到输入 WebSocket 服务。';
        processingError.value = errorMsg;
        isConnectedInput.value = false;
        isProcessing.value = false;
        reject(new Error(errorMsg)); // Reject the Promise on error
      };

      inputWs.value.onclose = (event) => {
        console.log('Input WebSocket disconnected:', event.reason);
        isConnectedInput.value = false;
        inputWs.value = null;
        // Reject if closed before task ID was assigned?
        if (!taskId.value && event.code !== 1000) {
            const errorMsg = "输入连接在分配任务 ID 前关闭。";
            if (!processingError.value) processingError.value = errorMsg;
            // Only reject if the promise hasn't already resolved/rejected
            // reject(new Error(errorMsg)); // Be careful not to reject multiple times
        };
      };
    }); // End of Promise constructor
  };

  const sendTextInput = (text) => {
    if (!inputWs.value || inputWs.value.readyState !== WebSocket.OPEN) {
      console.error('Input WebSocket is not connected.');
      processingError.value = '输入 WebSocket 未连接。';
      return;
    }
    if (!taskId.value) {
       console.error('Task ID not yet assigned.');
       processingError.value = '任务 ID 尚未分配。';
       // Maybe attempt to connect first? Or let UI handle this state.
       return;
    }

    console.log(`Sending text input (task ${taskId.value}):`, text);
    try {
      // 1. Send metadata JSON
      const metadata = {
        type: "text",
        chunk_id: 0,
        action: "data_chunk" // Recommended
      };
      inputWs.value.send(JSON.stringify(metadata));
      console.log('Sent text metadata:', metadata);

      // 2. Immediately send encoded text bytes
      const encodedText = new TextEncoder().encode(text);
      inputWs.value.send(encodedText);
      console.log('Sent text binary bytes, length:', encodedText.byteLength);

      // 3. Send upload complete signal
      const uploadCompleteSignal = { action: "upload_complete" };
      inputWs.value.send(JSON.stringify(uploadCompleteSignal));
      console.log('Sent upload_complete signal.');

    } catch (error) {
        console.error('Error sending text input:', error);
        processingError.value = '发送文本消息时出错。';
    }
  };

  const disconnectInput = () => {
    if (inputWs.value) {
      console.log('Disconnecting input WebSocket.');
      inputWs.value.close();
      inputWs.value = null; // Release the reference
    }
  };

  // --- Audio Reassembly ---
  const reassembleAndHandleAudio = () => {
      if (receivedAudioChunkCount.value !== expectedAudioChunks.value || audioChunks.value.length !== expectedAudioChunks.value) {
          console.error(`Audio reassembly error: Expected ${expectedAudioChunks.value} chunks, received ${receivedAudioChunkCount.value}. Array length: ${audioChunks.value.length}`);
          processingError.value = "音频数据接收不完整。";
          resetAudioState();
          return;
      }
      if (expectedAudioChunks.value === 0) {
          console.log("No audio chunks were expected or received.");
          return; // Nothing to reassemble
      }

      try {
          console.log("Reassembling audio from", audioChunks.value.length, "chunks...");
          // Ensure all chunks are valid before creating blob
          const validChunks = audioChunks.value.filter(chunk => chunk instanceof Blob || chunk instanceof ArrayBuffer);
          if (validChunks.length !== expectedAudioChunks.value) {
              throw new Error("Some received audio chunks are invalid.");
          }

          // 确认 MP3 为统一输出格式
          const completeAudioBlob = new Blob(validChunks, { type: 'audio/mpeg' });
          console.log("Audio reassembled successfully. Blob size:", completeAudioBlob.size);

          // Clean up previous URL if exists
          if (receivedAudioUrl.value) {
              URL.revokeObjectURL(receivedAudioUrl.value);
          }
          // Create Object URL for playback
          receivedAudioUrl.value = URL.createObjectURL(completeAudioBlob);
          console.log("Created audio object URL:", receivedAudioUrl.value);

      } catch (error) {
          console.error("Error reassembling audio:", error);
          processingError.value = "处理接收到的音频时出错。";
      } finally {
          // Reset audio chunk state after processing
          resetAudioState();
      }
  };

  const resetAudioState = () => {
      audioChunks.value = [];
      expectedAudioChunks.value = 0;
      receivedAudioChunkCount.value = 0;
      lastReceivedAudioChunkId.value = -1;
  };

  // --- Output WebSocket Handling ---

  const connectOutput = (currentTaskId) => {
     if (!currentTaskId) {
         console.error("Cannot connect to output: Task ID is missing.");
         processingError.value = "无法连接输出：缺少任务 ID。";
         return;
     }
     if (outputWs.value && outputWs.value.readyState === WebSocket.OPEN) {
         console.log('Output WebSocket already open for task:', currentTaskId);
         // If the task ID hasn't changed, do nothing. If it has, disconnect old and connect new?
         // For simplicity, assume we only connect once per task ID received from input.
         return;
     }

     const wsOutputUrl = buildOutputWsUrl(currentTaskId);
     console.log('Attempting to connect to output WebSocket:', wsOutputUrl);

     // Reset output-specific states
     isConnectedOutput.value = false;
     receivedText.value = '';
     processingError.value = null; // Clear previous output errors
     resetAudioState(); // Reset audio state for the new task
     if (receivedAudioUrl.value) { URL.revokeObjectURL(receivedAudioUrl.value); receivedAudioUrl.value = null; }

     outputWs.value = new WebSocket(wsOutputUrl);

     outputWs.value.onopen = () => {
       console.log('Output WebSocket connected for task:', currentTaskId);
       isConnectedOutput.value = true;
       // No longer processing the *upload*, but waiting for results
     };

     outputWs.value.onmessage = (event) => {
       console.log(`Output WebSocket message received (task ${currentTaskId}):`, event.data);

       // --- Handle Binary Data First (Audio Chunk) ---
       if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
           console.log(`Received binary audio data chunk (expecting ID ${lastReceivedAudioChunkId.value}).`);
           if (lastReceivedAudioChunkId.value !== -1 && lastReceivedAudioChunkId.value < expectedAudioChunks.value) {
               // Store the received chunk
               // Make sure the array is initialized
               if (audioChunks.value.length !== expectedAudioChunks.value && expectedAudioChunks.value > 0) {
                   console.warn(`Audio chunk array not initialized correctly. Expected ${expectedAudioChunks.value}, got ${audioChunks.value.length}. Reinitializing.`);
                   audioChunks.value = new Array(expectedAudioChunks.value);
               }
               if (lastReceivedAudioChunkId.value < audioChunks.value.length) {
                    audioChunks.value[lastReceivedAudioChunkId.value] = event.data; // Use Blob directly
                    receivedAudioChunkCount.value++;
                    console.log(`Stored audio chunk ${lastReceivedAudioChunkId.value}. Received ${receivedAudioChunkCount.value}/${expectedAudioChunks.value}`);
               } else {
                    console.error(`Received audio chunk with invalid index: ${lastReceivedAudioChunkId.value}`);
                    // Handle error? Maybe disconnect?
               }
               lastReceivedAudioChunkId.value = -1; // Reset, wait for next metadata chunk
           } else {
               console.warn("Received unexpected binary data when not expecting audio chunk ID:", lastReceivedAudioChunkId.value);
           }
           return; // Processed binary data, exit handler
       }

       // --- Handle JSON Data ---
       try {
         const message = JSON.parse(event.data);

         if (message.status === 'success' && message.task_id === currentTaskId) {
           console.log('Received successful text result:', message.content);
           receivedText.value = message.content || '';
           // If audio is NOT present, processing is fully complete.
           if (!message.audio_present) {
               isProcessing.value = false; // Processing complete
               disconnectOutput();
           } else {
               console.log("Audio is present, preparing to receive chunks...");
               // Reset audio state for receiving, wait for first audio_chunk metadata
               resetAudioState();
               // isProcessing remains true until audio_complete
           }
         } else if (message.type === 'audio_chunk' && message.task_id === currentTaskId) {
             console.log(`Received audio chunk metadata: ID ${message.chunk_id}/${message.total_chunks}`);
             if (message.chunk_id === 0) { // First chunk metadata
                 expectedAudioChunks.value = message.total_chunks || 0;
                 audioChunks.value = new Array(expectedAudioChunks.value); // Initialize array
                 receivedAudioChunkCount.value = 0; // Reset count
             }
             // Verify chunk_id continuity if needed
             lastReceivedAudioChunkId.value = message.chunk_id; // Set expectation for next binary msg
         } else if (message.type === 'audio_complete' && message.task_id === currentTaskId) {
             console.log('Received audio complete signal.');
             isProcessing.value = false; // All processing is now complete
             reassembleAndHandleAudio(); // Process the collected chunks
             disconnectOutput(); // Disconnect after processing audio
         } else if (message.status === 'error') {
           console.error('Output WebSocket error message:', message.error);
           processingError.value = message.error || '未知处理错误。';
           isProcessing.value = false;
           disconnectOutput();
         } else {
           console.warn('Received unknown message structure on output WebSocket:', message);
         }
       } catch (e) {
         console.error('Error parsing output WebSocket message:', e);
         processingError.value = '无法解析来自服务器的响应。';
         isProcessing.value = false;
         disconnectOutput(); // Disconnect on parsing error
       }
     };

     outputWs.value.onerror = (event) => {
       console.error('Output WebSocket error:', event);
       processingError.value = `无法连接到输出 WebSocket 服务 (Task: ${currentTaskId})。`;
       isConnectedOutput.value = false;
       isProcessing.value = false; // Reset processing state on error
     };

     outputWs.value.onclose = (event) => {
       console.log('Output WebSocket disconnected:', event.reason, 'Code:', event.code);
       isConnectedOutput.value = false;
       outputWs.value = null;
       // Reset processing state only if closed unexpectedly *while* processing
       if (isProcessing.value && event.code !== 1000) {
           isProcessing.value = false;
           if (!processingError.value) {
               processingError.value = "输出连接意外关闭。";
           }
       }
       // Clean up audio state if connection closes unexpectedly during audio reception
       if (expectedAudioChunks.value > 0 && receivedAudioChunkCount.value < expectedAudioChunks.value) {
            resetAudioState();
            if (!processingError.value) processingError.value = "音频传输未完成时连接关闭。";
       }
     };
  };

  const disconnectOutput = () => {
    if (outputWs.value) {
      console.log('Disconnecting output WebSocket.');
      outputWs.value.close(1000, "Client disconnecting normally"); // Send normal closure code
      // outputWs.value = null; // Let onclose handle this
    }
  };

  // --- Audio Recording Handling ---

  const startRecording = async () => {
      if (isRecording.value) {
          console.warn("Recording is already in progress.");
          return;
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          console.error("getUserMedia not supported on your browser!");
          recordingError.value = "您的浏览器不支持录音功能。";
          return;
      }

      console.log("Requesting microphone access...");
      recordingError.value = null; // Clear previous errors
      recordedAudioChunks.value = []; // Reset chunks

      try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          console.log("Microphone access granted.");

          // TODO: Consider specific MIME types supported by the backend (e.g., 'audio/wav', 'audio/webm')
          // Browsers might have different defaults or support levels. 'audio/webm;codecs=opus' is common.
          recorder.value = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

          recorder.value.ondataavailable = (event) => {
              if (event.data.size > 0) {
                  recordedAudioChunks.value.push(event.data);
                  console.log("Recorded chunk size:", event.data.size);
              }
          };

          recorder.value.onstop = () => {
              console.log("[useApi] MediaRecorder onstop event triggered.");
              console.log("Recording stopped. Total chunks:", recordedAudioChunks.value.length);
              isRecording.value = false;
              // Stop the tracks to release the microphone
              stream.getTracks().forEach(track => track.stop());
              // TODO: Trigger sending the collected audio chunks
              if (recordedAudioChunks.value.length > 0) {
                  sendAudioInput(); // Call the function to send data
              } else {
                  console.warn("No audio data recorded.");
              }
              console.log("[useApi] MediaRecorder onstop event handler finished.");
          };

          recorder.value.onerror = (event) => {
              console.error("MediaRecorder error:", event.error);
              recordingError.value = `录音出错: ${event.error.name}`;
              isRecording.value = false;
               // Stop the tracks on error as well
              stream.getTracks().forEach(track => track.stop());
          };

          recorder.value.start(); // Start recording
          isRecording.value = true;
          console.log("Recording started.");

      } catch (err) {
          console.error("Error accessing microphone:", err);
          if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
              recordingError.value = "未获得麦克风权限。请在浏览器设置中允许访问。";
          } else {
              recordingError.value = `无法访问麦克风: ${err.name}`;
          }
          isRecording.value = false; // Ensure recording state is false on error
      }
  };

  const stopRecording = () => {
      if (!isRecording.value || !recorder.value || recorder.value.state === 'inactive') {
          console.warn("[useApi] stopRecording called but not active or recorder invalid. State:", recorder.value?.state);
          return;
      }
      console.log("[useApi] stopRecording called. Current recorder state:", recorder.value.state);
      recorder.value.stop();
       // Note: Actual sending happens in the onstop handler
  };

  // --- Sending Audio Input ---
  // Placeholder for the actual audio sending logic
  const sendAudioInput = async () => {
      if (!recordedAudioChunks.value || recordedAudioChunks.value.length === 0) {
          console.error("No recorded audio data to send.");
          return;
      }
       console.log("Preparing to send recorded audio...");

      // 1. Ensure input WebSocket is connected and has a task ID
      if (!inputWs.value || inputWs.value.readyState !== WebSocket.OPEN || !taskId.value) {
          console.log("Input WebSocket not ready, attempting to connect...");
          try {
              // Use the existing connectInput logic which returns a Promise resolving with taskId
              await connectInput(); // This should set up inputWs and taskId
              if (!inputWs.value || inputWs.value.readyState !== WebSocket.OPEN || !taskId.value) {
                   throw new Error("Failed to establish input connection or get task ID after attempt.");
              }
              console.log("Input connection established for audio sending. Task ID:", taskId.value);
          } catch (error) {
              console.error("Failed to connect input WebSocket for audio sending:", error);
              processingError.value = "发送音频前无法连接到服务器。";
              isProcessing.value = false; // Ensure processing is stopped
              // Clear recorded chunks if connection fails? Or allow retry?
              // recordedAudioChunks.value = [];
              return;
          }
      }

      // 2. Combine recorded chunks into a single Blob
      // The backend expects chunks, but MediaRecorder gives chunks based on time slices or buffer fullness.
      // We might need to re-chunk the combined Blob if the backend has strict size limits,
      // or send the MediaRecorder chunks directly if the backend can handle variable sizes.
      // For simplicity now, let's assume we send the chunks as MediaRecorder produced them.

      console.log(`Sending ${recordedAudioChunks.value.length} audio chunks for task ${taskId.value}...`);
      processingError.value = null; // Clear previous errors
      isProcessing.value = true; // Start processing indicator
      uploadCompleteConfirmed.value = false; // Reset confirmation flag

      try {
          const chunksToSend = recordedAudioChunks.value; // Use the chunks directly

          // 3. Send chunks sequentially (metadata + binary)
          for (let i = 0; i < chunksToSend.length; i++) {
              const chunk = chunksToSend[i];
              const metadata = {
                  type: "audio", // Or recorder.value.mimeType if backend needs it?
                  chunk_id: i,
                  action: "data_chunk"
              };

              if (inputWs.value.readyState !== WebSocket.OPEN) {
                  throw new Error("Input WebSocket closed unexpectedly during audio chunk sending.");
              }
              inputWs.value.send(JSON.stringify(metadata));
              console.log(`Sent audio metadata chunk ${i}:`, metadata);

              // Wait a tiny moment for the JSON to likely be processed before sending binary? Might not be needed.
              // await new Promise(resolve => setTimeout(resolve, 5));

              if (inputWs.value.readyState !== WebSocket.OPEN) {
                 throw new Error("Input WebSocket closed unexpectedly before sending binary audio chunk.");
              }
              inputWs.value.send(chunk); // Send the Blob directly
              console.log(`Sent audio binary chunk ${i}, size: ${chunk.size}`);

              // Optional: Wait for 'File chunk received' confirmation? Could slow things down.
          }

          // 4. Send upload complete signal
           if (inputWs.value.readyState !== WebSocket.OPEN) {
              throw new Error("Input WebSocket closed unexpectedly before sending upload_complete.");
           }
          const uploadCompleteSignal = { action: "upload_complete" };
          inputWs.value.send(JSON.stringify(uploadCompleteSignal));
          console.log('Sent upload_complete signal for audio.');

          // 5. Cleanup recorded data after successful initiation of sending
          recordedAudioChunks.value = [];

          // Note: isProcessing will be set to false when the output WS receives the final result or error.
          // The input WS will disconnect itself upon receiving 'upload_processed'.

      } catch (error) {
          console.error("Error sending audio chunks:", error);
          processingError.value = `发送音频时出错: ${error.message}`;
          isProcessing.value = false; // Stop processing indicator on error
          // Consider disconnecting inputWS here on error? It might auto-close anyway.
          // disconnectInput();
          // disconnectInput();
          // Clear potentially partially sent data?
          recordedAudioChunks.value = [];
      }
  };

  // --- HTTP TTS 拉取已移除：仅保留双 WS 模式 ---

  // Return reactive refs and methods
  return {
    taskId,
    isConnectedInput,
    isConnectedOutput,
    isProcessing,
    uploadCompleteConfirmed,
    processingError,
    receivedText,
    receivedAudioUrl, // Export the audio URL
    // Export recording state and methods
    isRecording,
    recordingError,
    startRecording,
    stopRecording,
    // Export methods
    connectInput,
    sendTextInput,
    disconnectInput,
    disconnectOutput // connectOutput is called internally for now
  };
}
