import React, { useState, useRef, useEffect } from 'react';
import InsightsSidebar from '../components/InsightsSidebar';
import InsightsHeader from '../components/InsightsHeader';
import InsightsChatArea from '../components/InsightsChatArea';
import InsightsChatInput from '../components/InsightsChatInput';
import InsightsArtifactsPane from '../components/InsightsArtifactsPane';
import { geminiChatComplete, GeminiModel } from '../services/geminiApi';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useChats } from '../contexts/ChatsContext';
import { fastApiService } from '../services/fastApiService';

export interface ChatMessage {
  id: number;
  type: 'user' | 'ai';
  content: string;
  time: string;
}

const ChatInterface: React.FC = () => {
  const [selectedModel, setSelectedModel] = useState<GeminiModel>('gemini-2.5-flash-lite');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  const [showArtifacts, setShowArtifacts] = useState(true);
  const [chatTitle, setChatTitle] = useState<string>('');
  const [hasCreatedChat, setHasCreatedChat] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const { addChat, updateChat, getChat, currentChatId, setCurrentChatId } = useChats();

  // Load messages when currentChatId changes
  useEffect(() => {
    if (currentChatId) {
      const selectedChat = getChat(currentChatId);
      if (selectedChat) {
        setMessages(selectedChat.messages || []);
        setChatTitle(selectedChat.title);
        setHasCreatedChat(true);
      }
    } else {
      // Clear messages when no chat is selected
      setMessages([]);
      setChatTitle('');
      setHasCreatedChat(false);
    }
  }, [currentChatId, getChat]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    let cancelled = false;

    (async () => {
      try {
        const cfg = await fastApiService.getLLMConfig();
        if (cancelled) return;
        console.log('🔎 Backend LLM config (chat/KG/embedding):', cfg);
      } catch (e) {
        if (cancelled) return;
        console.warn('⚠️ Failed to fetch backend LLM config:', e);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-scroll to bottom when new messages are added or typing state changes
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  // Create a new chat only when user sends their first message
  const createNewChat = () => {
    if (!hasCreatedChat) {
      const newChatId = Date.now();
      setCurrentChatId(newChatId);
      addChat('New Chat', []);
      setHasCreatedChat(true);
    }
  };

  // Update chat title based on first user message
  const updateChatTitle = (userText: string) => {
    if (!chatTitle && currentChatId) {
      const title = userText.length > 30 ? userText.substring(0, 30) + '...' : userText;
      setChatTitle(title);
      updateChat(currentChatId, { title });
    }
  };

  // Send a new user message and get Gemini response
  const handleSend = async (userText: string) => {
    if (!userText.trim()) return;
    
    // Create new chat on first message if no chat is selected
    if (!currentChatId) {
      createNewChat();
    }
    
    const userMsg: ChatMessage = {
      id: Date.now(),
      type: 'user',
      content: userText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    setMessages(prev => [...prev, userMsg]);
    
    // Update chat title on first message
    updateChatTitle(userText);
    
    setIsTyping(true);
    
    // Call Gemini API
    const aiText = await geminiChatComplete({
      prompt: userText,
      model: selectedModel,
      history: messages.map(m => ({ role: m.type === 'user' ? 'user' : 'model', parts: [m.content] }))
    });
    
    const aiMsg: ChatMessage = {
      id: Date.now() + 1,
      type: 'ai',
      content: aiText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    setMessages(prev => [...prev, aiMsg]);
    setIsTyping(false);
    
    // Update chat with new messages
    if (currentChatId) {
      updateChat(currentChatId, { 
        messages: [...messages, userMsg, aiMsg],
        time: 'Just now'
      });
    }
  };

  // Edit a previous user message
  const handleEdit = (msg: ChatMessage) => {
    setEditingId(msg.id);
    setEditValue(msg.content);
  };
  
  const handleEditSave = async () => {
    if (editingId === null) return;
    
    setMessages(prev => prev.map(m => m.id === editingId ? { ...m, content: editValue } : m));
    
    // Regenerate AI response for this message
    const idx = messages.findIndex(m => m.id === editingId);
    if (idx !== -1) {
      setIsTyping(true);
      const aiText = await geminiChatComplete({
        prompt: editValue,
        model: selectedModel,
        history: messages.slice(0, idx).map(m => ({ role: m.type === 'user' ? 'user' : 'model', parts: [m.content] }))
      });
      
      // Replace the next AI message (if any) or insert after
      setMessages(prev => {
        const newMsgs = [...prev];
        const aiIdx = newMsgs.findIndex((m, i) => i > idx && m.type === 'ai');
        const aiMsg: ChatMessage = {
          id: Date.now() + 2,
          type: 'ai',
          content: aiText,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        if (aiIdx !== -1) {
          newMsgs[aiIdx] = aiMsg;
        } else {
          newMsgs.splice(idx + 1, 0, aiMsg);
        }
        return newMsgs;
      });
      
      setIsTyping(false);
      
      // Update chat with edited messages
      if (currentChatId) {
        const updatedMessages = messages.map(m => m.id === editingId ? { ...m, content: editValue } : m);
        updateChat(currentChatId, { messages: updatedMessages });
      }
    }
    
    setEditingId(null);
    setEditValue('');
  };
  
  const handleEditCancel = () => {
    setEditingId(null);
    setEditValue('');
  };

  // Regenerate AI response for a specific user message
  const handleRegenerate = async (userMsgId: number) => {
    const userMsg = messages.find(m => m.id === userMsgId);
    if (!userMsg) return;
    
    setIsTyping(true);
    const aiText = await geminiChatComplete({
      prompt: userMsg.content,
      model: selectedModel,
      history: messages.slice(0, messages.findIndex(m => m.id === userMsgId)).map(m => ({ role: m.type === 'user' ? 'user' : 'model', parts: [m.content] }))
    });
    
    const aiMsg: ChatMessage = {
      id: Date.now() + 3,
      type: 'ai',
      content: aiText,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    // Replace the AI message that follows the user message
    setMessages(prev => {
      const newMsgs = [...prev];
      const userIdx = newMsgs.findIndex(m => m.id === userMsgId);
      const aiIdx = newMsgs.findIndex((m, i) => i > userIdx && m.type === 'ai');
      if (aiIdx !== -1) {
        newMsgs[aiIdx] = aiMsg;
      } else {
        newMsgs.splice(userIdx + 1, 0, aiMsg);
      }
      return newMsgs;
    });
    
    setIsTyping(false);
    
    // Update chat with regenerated messages
    if (currentChatId) {
      const updatedMessages = [...messages];
      const userIdx = updatedMessages.findIndex(m => m.id === userMsgId);
      const aiIdx = updatedMessages.findIndex((m, i) => i > userIdx && m.type === 'ai');
      if (aiIdx !== -1) {
        updatedMessages[aiIdx] = aiMsg;
      } else {
        updatedMessages.splice(userIdx + 1, 0, aiMsg);
      }
      updateChat(currentChatId, { messages: updatedMessages });
    }
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-blue-50 to-teal-50 dark:from-gray-900 dark:to-gray-800 overflow-hidden">
      {/* Sidebar */}
      <InsightsSidebar />
      
      {/* Main Area */}
      <div className="flex flex-col flex-1 min-w-0">
        <InsightsHeader selectedModel={selectedModel} onModelChange={setSelectedModel} />
        <div className="flex flex-1 min-h-0">
          {/* Chat Area */}
          <div className="h-full flex flex-col min-h-0 flex-1 bg-gradient-to-br from-white to-blue-50 dark:from-gray-900 dark:to-gray-800">
            <div
              ref={chatContainerRef}
              className="flex-1 min-h-0 overflow-y-auto max-h-[70vh]"
            >
              <InsightsChatArea
                messages={messages}
                editingId={editingId}
                editValue={editValue}
                isTyping={isTyping}
                onEdit={handleEdit}
                onEditChange={setEditValue}
                onEditSave={handleEditSave}
                onEditCancel={handleEditCancel}
                onRegenerate={handleRegenerate}
              />
            </div>
            <div className="shrink-0">
              <InsightsChatInput
                onSend={handleSend}
                isTyping={isTyping}
              />
            </div>
          </div>
          
          {/* Artifacts Pane */}
          {showArtifacts && (
            <InsightsArtifactsPane
              onToggle={() => setShowArtifacts(false)}
            />
          )}
          
          {/* Show Artifacts Button (when hidden) */}
          {!showArtifacts && (
            <div className="flex items-center justify-center w-6 bg-gray-200 dark:bg-gray-700 border-l border-gray-300 dark:border-gray-600 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors">
              <button
                onClick={() => setShowArtifacts(true)}
                className="p-1 rounded hover:bg-gray-400 transition-colors"
                title="Show Artifacts"
              >
                <ChevronLeft className="h-4 w-4 text-gray-700 dark:text-gray-300" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;