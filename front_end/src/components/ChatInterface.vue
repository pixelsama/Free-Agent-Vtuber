<template>
  <div class="d-flex flex-column chat-container">
    <v-list class="flex-grow-1 overflow-y-auto pa-4 chat-messages" ref="chatListRef">
      <!-- Removed static examples -->
      <transition-group name="message" tag="div" class="message-list">
        <div v-for="(message, index) in messages" :key="message.id || index"
             :class="['message-wrapper', 'd-flex', message.sender === 'user' ? 'justify-end' : 'align-start', 'mb-3', index === 0 ? 'mt-4' : '']">
           <!-- AI Avatar (only for received messages) -->
           <v-avatar v-if="message.sender === 'ai'" size="40" class="mr-3">
               <v-icon>mdi-robot-happy-outline</v-icon> <!-- Using a robot icon for AI -->
           </v-avatar>
           <!-- User Avatar Placeholder (only for user messages - optional) -->
           <!-- <v-avatar v-if="message.sender === 'user'" size="40" class="ml-3 order-last">
               <v-icon>mdi-account</v-icon>
           </v-avatar> -->

           <div :class="['message-bubble', message.sender]">
              <!-- Display text content -->
              <span v-if="message.text">{{ message.text }}</span>
              <!-- Placeholder for loading AI response -->
              <v-progress-circular
                v-if="message.sender === 'ai' && message.loading"
                indeterminate
                color="primary"
                size="20"
                width="2"
              ></v-progress-circular>
              <!-- Display error message -->
              <span v-if="message.sender === 'system'" class="error-text">
                  <v-icon small color="error" class="mr-1">mdi-alert-circle-outline</v-icon>
                  {{ message.text }}
              </span>
           </div>
        </div>
      </transition-group>
    </v-list>

    <v-sheet class="pa-4 message-input-area" elevation="0">
       <!-- Optional: Display Connection/Processing Status -->
       <div class="status-bar text-caption mb-2 d-flex justify-space-between">
           <span>输入: {{ isConnectedInput ? '已连接' : '未连接' }} | 输出: {{ isConnectedOutput ? '已连接' : '未连接' }}</span>
           <span v-if="isProcessing" class="text-blue">处理中...</span>
           <span v-if="processingError" class="text-error">{{ processingError }}</span>
       </div>
      <v-row align="center" no-gutters>
        <v-col cols="auto" class="mr-2">
          <v-btn icon variant="text" density="compact" :disabled="isProcessing">
            <v-icon color="#49454F">mdi-plus-circle-outline</v-icon>
          </v-btn>
        </v-col>
        <v-col cols="auto">
          <v-btn icon variant="text" density="compact" :disabled="isProcessing">
             <v-icon color="#49454F">mdi-emoticon-happy-outline</v-icon>
          </v-btn>
        </v-col>
        <v-col>
          <v-text-field
            v-model="newMessage"
            placeholder="输入消息..."
            variant="solo"
            rounded
            density="compact"
            hide-details
            bg-color="#ECE6F0"
            flat
            @keydown.enter.prevent="sendMessage"
            :readonly="isRecording" 
            :disabled="isProcessing" 
            :loading="isProcessing"
          >
            <template v-slot:append-inner>
              <v-btn 
                icon 
                variant="text" 
                density="compact" 
                @click="toggleRecording"
                :disabled="isProcessing" 
                :color="isRecording ? 'red' : '#49454F'" 
              >
                <v-icon>{{ isRecording ? 'mdi-stop-circle' : 'mdi-microphone' }}</v-icon>
              </v-btn>
            </template>
          </v-text-field>
        </v-col>
      </v-row>
    </v-sheet>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue';
import { useApi } from '@/composables/useApi'; // Adjust path if needed

// --- Reactive State ---
const newMessage = ref('');
const messages = ref([
    // Initial welcome message or leave empty
    // { sender: 'ai', text: '你好！有什么可以帮你的吗？' }
]);
const chatListRef = ref(null); // Ref for the message list container

// --- API Composable ---
const {
  taskId,
  isConnectedInput,
  isConnectedOutput,
  isProcessing,
  processingError,
  receivedText,
  receivedAudioUrl, // Import this to potentially display/play received audio later
  connectInput,
  sendTextInput,
  // Recording related imports
  isRecording,
  recordingError,
  startRecording,
  stopRecording,
  // disconnectInput, // Not called directly from component usually
  // disconnectOutput // Not called directly from component usually
} = useApi();

// --- Methods ---
const scrollToBottom = () => {
  nextTick(() => {
    const chatList = chatListRef.value?.$el || chatListRef.value; // Access underlying element
    if (chatList) {
      chatList.scrollTop = chatList.scrollHeight;
    }
  });
};

const sendMessage = async () => {
  const text = newMessage.value.trim();
  if (!text || isProcessing.value) return; // Don't send empty messages or while processing

  // 1. Add user message to UI
  messages.value.push({ sender: 'user', text: text, id: Date.now() + Math.random() });
  const userMessageText = newMessage.value; // Store before clearing
  newMessage.value = '';
  scrollToBottom();

  // Don't add loading message immediately, wait for backend response


  try {
    // 2. Connect and get task ID (or use existing connection if open)
    console.log('Connecting input...');
    processingError.value = null; // Clear previous errors before sending
    await connectInput(); // Wait for connection and task ID

    // 3. Send the text input
    console.log('Sending text input...');
    sendTextInput(userMessageText);

    // isProcessing is set true by useApi when upload is confirmed queued
    // Wait for response via watch effect

  } catch (error) {
    console.error('Error in sendMessage:', error);
    // Remove the AI loading message
    messages.value = messages.value.filter(m => m.id !== aiLoadingMessage.id);
     // Display connection error (processingError is already set by useApi)
    // messages.value.push({ sender: 'system', text: processingError.value || '发送消息时出错。' }); // Commented out to avoid duplicate error display
    scrollToBottom();
    // Reset processing state? useApi might already handle this on error.
  }
};

const toggleRecording = () => {
  if (isRecording.value) {
    stopRecording();
  } else {
    // Clear any previous message before starting recording
    newMessage.value = '';
    startRecording();
  }
};

// --- Watchers ---

// Watch for AI text response
watch(receivedText, (newText) => {
  if (newText) {
    // Add the actual AI response directly (no loading message to remove)
    messages.value.push({ sender: 'ai', text: newText, id: Date.now() + Math.random() });
    scrollToBottom();
    // Reset receivedText in composable? Or assume it's only set once per response.
     receivedText.value = ''; // Clear it after processing
  }
});

// Watch for processing errors after connection
watch(processingError, (newError) => {
  if (newError && isProcessing.value) { // Only show errors that occur *during* processing
    // Add error message to chat (no loading message to remove)
    messages.value.push({ sender: 'system', text: newError, id: Date.now() + Math.random() });
    scrollToBottom();
     // Reset processing state? useApi sets isProcessing false on error
  }
   // Consider clearing processingError after displaying?
   // processingError.value = null; // Maybe do this in useApi or based on user action
});

// Watch for recording errors
watch(recordingError, (newError) => {
  if (newError) {
    // Display recording error in the chat
    messages.value.push({ sender: 'system', text: `录音错误: ${newError}`, id: Date.now() + Math.random() });
    scrollToBottom();
    // Consider clearing the error after showing it, or let useApi handle reset
    // recordingError.value = null;
  }
});

// Initial connection attempt (optional, can connect on first message)
onMounted(() => {
  connectInput().catch(err => console.error("Initial connection failed:", err));
});

</script>

<style scoped>
.chat-container {
  height: 100%;
  background-color: white;
}

.chat-messages {
  /* Styles for message list - already has overflow etc. */
}

.message-input-area {
  border-top: 1px solid #e0e0e0;
  background-color: white; /* Ensure input area bg is white */
}

.message-wrapper {
  width: 100%;
}

.message-bubble {
  padding: 8px 16px;
  border-radius: 20px;
  max-width: 80%;
  word-wrap: break-word;
  line-height: 1.4;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.message-bubble.user { /* Renamed from sent for clarity */
  background-color: #625B71;
  color: white;
  border-bottom-right-radius: 8px;
  margin-left: auto;
}

.message-bubble.ai { /* Renamed from received */
  background-color: #ECE6F0;
  color: #1D1B20;
  border-bottom-left-radius: 8px;
  margin-right: auto;
}

.message-bubble.system { /* Style for system/error messages */
    background-color: #fceded; /* Light error background */
    color: #b71c1c; /* Dark error text */
    border-radius: 8px;
    max-width: 90%;
    margin-left: auto;
    margin-right: auto;
    text-align: center;
    font-size: 0.9em;
    padding: 6px 12px;
}
.error-text {
    display: flex;
    align-items: center;
}


/* Ensure avatar images are round */
.v-avatar img {
    border-radius: 50%;
    object-fit: cover;
}

/* Status bar styling */
.status-bar {
    color: #757575; /* Grey text */
    padding: 0 8px;
}
.text-blue { color: #1976D2; }
.text-error { color: #D32F2F; }

/* Message animation styles - Telegram-like scale and fade in */
.message-enter-active {
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.message-leave-active {
  transition: all 0.2s ease-in;
}

.message-enter-from {
  opacity: 0;
  transform: scale(0.3);
}

.message-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

.message-move {
  transition: transform 0.3s ease;
}

/* Enhanced bubble animation with color transition */
.message-bubble {
  transition: all 0.2s ease;
  animation-fill-mode: both;
}

.message-bubble:hover {
  transform: translateY(-1px) scale(1.02);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

/* Color animation for user messages */
.message-bubble.user {
  animation: userBubbleColorFade 0.4s ease-out;
}

@keyframes userBubbleColorFade {
  0% {
    background-color: #9C8AA6;
  }
  50% {
    background-color: #7A6B85;
  }
  100% {
    background-color: #625B71;
  }
}

/* Color animation for AI messages */
.message-bubble.ai {
  animation: aiBubbleColorFade 0.4s ease-out;
}

@keyframes aiBubbleColorFade {
  0% {
    background-color: #F5F1F8;
  }
  50% {
    background-color: #F0EBF4;
  }
  100% {
    background-color: #ECE6F0;
  }
}

</style>