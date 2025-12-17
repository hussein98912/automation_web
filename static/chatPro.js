// chatbot-sdk.js - Enhanced Chatbot SDK with Responsive Design & Smooth Animations
(function (window, document) {
    'use strict';

    // Default Configuration
    const DEFAULT_CONFIG = {
        widgetPosition: 'bottom-right',
        primaryColor: '#3b82f6',
        accentColor: '#8b5cf6',
        greetingMessage: "Hello! I'm your chatbot assistant. How can I help you today?",
        autoInit: true,
        autoOpen: false,
        animationDuration: 300,
        mobileBreakpoint: 640 // Width in pixels
    };

    // State
    let isInitialized = false;
    let isOpen = false;
    let messages = [];
    let sessionId = null;
    let config = { ...DEFAULT_CONFIG };

    // Generate unique session ID
    function generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Validate required configuration
    function validateConfig(userConfig) {
        if (!userConfig.agentId) {
            console.error('Chatbot SDK: agentId is required');
            return false;
        }
        if (!userConfig.apiKey) {
            console.error('Chatbot SDK: apiKey is required');
            return false;
        }
        return true;
    }

    // Check if device is mobile
    function isMobile() {
        return window.innerWidth <= config.mobileBreakpoint;
    }

    // Create chatbot widget
    function createWidget() {
        // Check if widget already exists
        if (document.getElementById('chatbot-widget-container')) {
            console.warn('Chatbot SDK: Widget already exists');
            return;
        }

        sessionId = generateSessionId();

        // Create container
        const container = document.createElement('div');
        container.id = 'chatbot-widget-container';
        container.className = 'chatbot-widget-container';
        container.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 9999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            pointer-events: none;
        `;

        // Create toggle button
        const toggleButton = document.createElement('button');
        toggleButton.id = 'chatbot-toggle';
        toggleButton.className = 'chatbot-toggle-button';
        toggleButton.setAttribute('aria-label', 'Open chat');
        toggleButton.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
        `;
        toggleButton.style.cssText = `
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: linear-gradient(135deg, ${config.primaryColor}, ${config.accentColor});
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            transition: all ${config.animationDuration}ms ease;
            pointer-events: auto;
            position: relative;
            z-index: 10001;
        `;

        // Hover effects
        toggleButton.addEventListener('mouseenter', () => {
            if (!isOpen) {
                toggleButton.style.transform = 'scale(1.1)';
                toggleButton.style.boxShadow = '0 6px 25px rgba(0, 0, 0, 0.3)';
            }
        });

        toggleButton.addEventListener('mouseleave', () => {
            if (!isOpen) {
                toggleButton.style.transform = 'scale(1)';
                toggleButton.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.2)';
            }
        });

        toggleButton.addEventListener('click', toggleChatWindow);

        // Create chat window
        const chatWindow = document.createElement('div');
        chatWindow.id = 'chatbot-window';
        chatWindow.className = 'chatbot-window';
        chatWindow.style.cssText = `
            position: absolute;
            bottom: 70px;
            right: 0;
            width: 380px;
            max-width: calc(100vw - 48px);
            height: 500px;
            max-height: calc(100vh - 120px);
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border: 1px solid #e5e7eb;
            opacity: 0;
            transform: translateY(20px) scale(0.95);
            transition: all ${config.animationDuration}ms cubic-bezier(0.4, 0, 0.2, 1);
            pointer-events: none;
            z-index: 10000;
        `;

        // Update for mobile
        if (isMobile()) {
            chatWindow.style.cssText += `
                bottom: 70px;
                right: 12px;
                left: 12px;
                width: auto;
                height: 70vh;
            `;
        }

        // Chat window HTML
        chatWindow.innerHTML = `
            <div class="chatbot-header" style="
                padding: 16px;
                background: linear-gradient(135deg, ${config.primaryColor}20, ${config.accentColor}20);
                border-bottom: 1px solid #e5e7eb;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-shrink: 0;
                overflow: hidden;

            ">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="${config.primaryColor}" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: #111827;">Chat Assistant</h3>
                </div>
                <button id="chatbot-close" class="chatbot-close-button" style="
                    background: none;
                    border: none;
                    cursor: pointer;
                    padding: 4px;
                    border-radius: 4px;
                    color: #6b7280;
                    font-size: 18px;
                    transition: background-color 0.2s;
                ">✕</button>
            </div>
            
            <div id="chatbot-messages" class="chatbot-messages" style="
                flex: 1;
                padding: 16px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 12px;
                min-height: 0;
            ">
                <div class="chatbot-message chatbot-message-assistant">
                    <div class="chatbot-message-bubble chatbot-message-bubble-assistant">
                        <p>${config.greetingMessage}</p>
                    </div>
                </div>
            </div>
            
            <div class="chatbot-input-container" style="
                padding: 16px;
                border-top: 1px solid #e5e7eb;
                background: white;
                flex-shrink: 0;
            ">
                <div style="display: flex; gap: 8px;">
                 <textarea 
    id="chatbot-input" 
    class="chatbot-input"
    placeholder="Type your message..."
    rows="1"
    style="
        flex: 1;
        padding: 12px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        resize: none;
        font-family: inherit;
        font-size: 14px;
        outline: none;
        transition: border-color 0.2s;
        min-height: 44px;
        box-sizing: border-box;
        overflow: hidden;   /* <-- ADD THIS */
    "
></textarea>

                    <button id="chatbot-send" class="chatbot-send-button" style="
                        padding: 12px 16px;
                        background: linear-gradient(135deg, ${config.primaryColor}, ${config.accentColor});
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-weight: 500;
                        transition: opacity 0.2s;
                        align-self: flex-end;
                        height: 44px;
                    ">Send</button>
                </div>
            </div>
        `;

        // Append elements
        container.appendChild(toggleButton);
        container.appendChild(chatWindow);
        document.body.appendChild(container);

        // Add event listeners
        document.getElementById('chatbot-close').addEventListener('click', toggleChatWindow);
        document.getElementById('chatbot-send').addEventListener('click', sendMessage);

        const textarea = document.getElementById('chatbot-input');
        textarea.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Auto-resize textarea
        textarea.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 100) + 'px';
        });

        // Initialize messages
        messages = [
            { role: 'assistant', content: config.greetingMessage, timestamp: new Date().toISOString() }
        ];

        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .chatbot-message {
                display: flex;
                margin-bottom: 12px;
                animation: fadeIn ${config.animationDuration}ms ease;
            }
            
            .chatbot-message-user {
                justify-content: flex-end;
            }
            
            .chatbot-message-assistant {
                justify-content: flex-start;
            }
            
            .chatbot-message-bubble {
                padding: 12px;
                border-radius: 12px;
                max-width: 80%;
                font-size: 14px;
                animation: slideIn ${config.animationDuration}ms ease;
            }
            
            .chatbot-message-bubble-user {
                background: linear-gradient(135deg, ${config.primaryColor}, ${config.accentColor});
                color: white;
                margin-left: 20%;
            }
            
            .chatbot-message-bubble-assistant {
                background: #f3f4f6;
                color: #374151;
            }
            
            .chatbot-message-bubble p {
                margin: 0;
                white-space: pre-wrap;
                word-break: break-word;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            @keyframes bounce {
                0%, 60%, 100% { transform: translateY(0); }
                30% { transform: translateY(-6px); }
            }
            
            .chatbot-typing-indicator {
                display: flex;
                align-items: center;
                gap: 4px;
                padding: 8px 12px;
            }
            
            /* Mobile optimizations */
            @media (max-width: ${config.mobileBreakpoint}px) {
                .chatbot-widget-container {
                    bottom: 12px;
                    right: 12px;
                    left: 12px;
                }
                
                .chatbot-toggle-button {
                    width: 52px;
                    height: 52px;
                }
                
                .chatbot-message-bubble {
                    max-width: 85%;
                }
                
                .chatbot-message-bubble-user {
                    margin-left: 15%;
                }
            }
            
            /* Smooth scrolling */
            #chatbot-messages {
                scroll-behavior: smooth;
            }
            
            /* Prevent body scroll when chat is open on mobile */
            .chatbot-open {
                overflow: hidden;
            }
        `;
        document.head.appendChild(style);

        console.log('Chatbot SDK: Widget initialized successfully');
    }

    // Toggle chat window with smooth animations
    function toggleChatWindow() {
        const chatWindow = document.getElementById('chatbot-window');
        const toggleButton = document.getElementById('chatbot-toggle');
        const container = document.getElementById('chatbot-widget-container');

        if (!chatWindow || !toggleButton || !container) return;

        isOpen = !isOpen;

        if (isOpen) {
            // Enable pointer events on container
            container.style.pointerEvents = 'auto';

            // Show chat window
            chatWindow.style.pointerEvents = 'auto';
            chatWindow.style.display = 'flex';

            // Force reflow to enable transition
            chatWindow.offsetHeight;

            // Animate in
            chatWindow.style.opacity = '1';
            chatWindow.style.transform = 'translateY(0) scale(1)';

            // Animate button
            toggleButton.style.transform = 'rotate(90deg) scale(1.1)';
            toggleButton.style.boxShadow = '0 6px 25px rgba(0, 0, 0, 0.3)';

            // Prevent body scroll on mobile
            if (isMobile()) {
                document.body.classList.add('chatbot-open');
            }

            // Focus and scroll after animation
            setTimeout(() => {
                const input = document.getElementById('chatbot-input');
                if (input) {
                    input.focus();
                }

                scrollToBottom();
            }, config.animationDuration);

        } else {
            // Animate out
            chatWindow.style.opacity = '0';
            chatWindow.style.transform = 'translateY(20px) scale(0.95)';

            // Reset button
            toggleButton.style.transform = 'rotate(0) scale(1)';
            toggleButton.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.2)';

            // Allow body scroll on mobile
            if (isMobile()) {
                document.body.classList.remove('chatbot-open');
            }

            // Hide after animation
            setTimeout(() => {
                chatWindow.style.display = 'none';
                chatWindow.style.pointerEvents = 'none';
                container.style.pointerEvents = 'none';
            }, config.animationDuration);
        }
    }

    // Add message to UI with animation
    function addMessageToUI(role, content) {
        const messagesContainer = document.getElementById('chatbot-messages');
        if (!messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `chatbot-message chatbot-message-${role}`;
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(10px)';

        const bubble = document.createElement('div');
        bubble.className = `chatbot-message-bubble chatbot-message-bubble-${role}`;

        // Handle typing indicator
        if (role === 'assistant' && content === '__TYPING__') {
            bubble.className = 'chatbot-message-bubble chatbot-message-bubble-assistant chatbot-typing-indicator';
            bubble.innerHTML = `
                <div style="display: flex; align-items: center; gap: 4px; height: 20px;">
                    <div style="
                        width: 6px;
                        height: 6px;
                        border-radius: 50%;
                        background: ${config.primaryColor};
                        animation: bounce 1.4s infinite;
                    "></div>
                    <div style="
                        width: 6px;
                        height: 6px;
                        border-radius: 50%;
                        background: ${config.primaryColor};
                        animation: bounce 1.4s infinite 0.2s;
                    "></div>
                    <div style="
                        width: 6px;
                        height: 6px;
                        border-radius: 50%;
                        background: ${config.primaryColor};
                        animation: bounce 1.4s infinite 0.4s;
                    "></div>
                </div>
            `;
        } else {
            bubble.innerHTML = `<p>${escapeHtml(content)}</p>`;
        }

        messageDiv.appendChild(bubble);
        messagesContainer.appendChild(messageDiv);

        // Animate message in
        setTimeout(() => {
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
            messageDiv.style.transition = `opacity ${config.animationDuration}ms ease, transform ${config.animationDuration}ms ease`;
        }, 10);

        scrollToBottom();
    }

    // Scroll to bottom of messages
    function scrollToBottom() {
        const messagesContainer = document.getElementById('chatbot-messages');
        if (messagesContainer) {
            setTimeout(() => {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }, 50);
        }
    }

    // Remove typing indicator
    function removeTypingIndicator() {
        const messagesContainer = document.getElementById('chatbot-messages');
        if (!messagesContainer) return;

        const typingIndicator = messagesContainer.querySelector('.chatbot-typing-indicator');
        if (typingIndicator) {
            typingIndicator.parentElement.remove();
        }
    }

    // HTML escape function for security
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Make API call to chatbot endpoint
    async function callChatbotAPI(message) {
        try {
            const response = await fetch('https://automation-web.onrender.com/Sdk/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    api_key: config.apiKey,
                    bot_id: config.agentId,
                    message: message,
                    session_id: sessionId,
                    timestamp: new Date().toISOString()
                })
            });

            if (!response.ok) {
                throw new Error(`API request failed with status ${response.status}`);
            }

            const data = await response.json();
            return data.response || data.message || "I received your message but didn't get a proper response.";

        } catch (error) {
            console.error('Chatbot SDK: API call failed', error);
            return "Sorry, I'm having trouble connecting to the server. Please try again later.";
        }
    }

    // Send message
    async function sendMessage() {
        const input = document.getElementById('chatbot-input');
        const message = input.value.trim();

        if (!message) return;

        // Add user message
        addMessageToUI('user', message);
        messages.push({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });

        // Clear input and reset height
        input.value = '';
        input.style.height = 'auto';

        // Add typing indicator
        addMessageToUI('assistant', '__TYPING__');

        try {
            // Call the chatbot API
            const response = await callChatbotAPI(message);

            // Remove typing indicator
            removeTypingIndicator();

            // Add assistant response
            addMessageToUI('assistant', response);
            messages.push({
                role: 'assistant',
                content: response,
                timestamp: new Date().toISOString()
            });

            console.log('Chatbot SDK: Message processed successfully', {
                sessionId,
                agentId: config.agentId
            });

        } catch (error) {
            // Remove typing indicator
            removeTypingIndicator();

            // Add error message
            const errorMessage = "Sorry, I encountered an error. Please try again.";
            addMessageToUI('assistant', errorMessage);
            messages.push({
                role: 'assistant',
                content: errorMessage,
                timestamp: new Date().toISOString()
            });

            console.error('Chatbot SDK: Error processing message', error);
        }
    }

    // Handle window resize
    function handleResize() {
        const chatWindow = document.getElementById('chatbot-window');
        if (chatWindow) {
            if (isMobile()) {
                chatWindow.style.cssText += `
                    bottom: 70px;
                    right: 12px;
                    left: 12px;
                    width: auto;
                    height: 70vh;
                `;
            } else {
                chatWindow.style.cssText += `
                    bottom: 70px;
                    right: 0;
                    left: auto;
                    width: 380px;
                    height: 500px;
                `;
            }
        }
    }

    // Public API methods
    const publicAPI = {
        toggle: toggleChatWindow,
        getSessionId: () => sessionId,
        getMessages: () => [...messages],
        sendMessage: async (text) => {
            if (text && typeof text === 'string') {
                const input = document.getElementById('chatbot-input');
                if (input) {
                    input.value = text;
                    await sendMessage();
                }
            }
        },
        open: () => {
            if (!isOpen) toggleChatWindow();
        },
        close: () => {
            if (isOpen) toggleChatWindow();
        },
        destroy: () => {
            const container = document.getElementById('chatbot-widget-container');
            if (container) {
                container.remove();
                isInitialized = false;
                window.removeEventListener('resize', handleResize);
                console.log('Chatbot SDK: Widget destroyed');
            }
        },
        updateConfig: (newConfig) => {
            if (isInitialized) {
                console.warn('Chatbot SDK: Cannot update config after initialization');
                return false;
            }
            config = { ...config, ...newConfig };
            return true;
        }
    };

    // Initialize SDK
    function init(options = {}) {
        if (isInitialized) {
            console.warn('Chatbot SDK is already initialized');
            return publicAPI;
        }

        // Validate required options
        if (!validateConfig(options)) {
            console.error('Chatbot SDK: Initialization failed due to missing required parameters');
            return null;
        }

        // Merge options with default config
        config = { ...DEFAULT_CONFIG, ...options };

        // Wait for DOM to be ready
        function initialize() {
            createWidget();
            isInitialized = true;
            console.log('Chatbot SDK: Initialized with agentId:', config.agentId);

            // Add resize listener
            window.addEventListener('resize', handleResize);

            // Auto-open if specified
            if (config.autoOpen) {
                setTimeout(() => toggleChatWindow(), 1000);
            }
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initialize);
        } else {
            initialize();
        }

        return publicAPI;
    }

    // Auto-initialize if script tag has data-config attribute
    function autoInitialize() {
        const script = document.currentScript;
        if (script && script.hasAttribute('data-config')) {
            try {
                const config = JSON.parse(script.getAttribute('data-config'));
                if (validateConfig(config)) {
                    window.ChatbotSDK = init(config);
                }
            } catch (error) {
                console.error('Chatbot SDK: Failed to parse data-config attribute', error);
            }
        }
    }

    // Expose to window
    window.ChatbotSDK = {
        init: init,
        version: '2.2.0'
    };

    // Auto-initialize when script loads
    autoInitialize();

})(window, document);