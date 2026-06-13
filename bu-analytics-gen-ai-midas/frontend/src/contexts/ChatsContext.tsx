import React, { createContext, useContext, useState, ReactNode } from 'react';

interface Chat {
  id: number;
  title: string;
  time: string;
  isBookmarked?: boolean;
  messages?: any[];
}

interface ChatsContextType {
  chats: Chat[];
  addChat: (title: string, messages?: any[]) => void;
  updateChat: (id: number, updates: Partial<Chat>) => void;
  deleteChat: (id: number) => void;
  bookmarkChat: (id: number) => void;
  getChats: () => Chat[];
  getChat: (id: number) => Chat | undefined;
  setCurrentChatId: (id: number | null) => void;
  currentChatId: number | null;
}

const ChatsContext = createContext<ChatsContextType | undefined>(undefined);

export const useChats = () => {
  const context = useContext(ChatsContext);
  if (context === undefined) {
    throw new Error('useChats must be used within a ChatsProvider');
  }
  return context;
};

interface ChatsProviderProps {
  children: ReactNode;
}

export const ChatsProvider: React.FC<ChatsProviderProps> = ({ children }) => {
  const [chats, setChats] = useState<Chat[]>([
    { id: 1, title: 'Credit Risk Analysis', time: '2h ago' },
    { id: 2, title: 'Portfolio Insights', time: '1d ago' },
    { id: 3, title: 'Fraud Detection', time: '3d ago' },
  ]);
  const [currentChatId, setCurrentChatId] = useState<number | null>(null);

  const addChat = (title: string, messages?: any[]) => {
    const newChat: Chat = {
      id: Date.now(),
      title: title,
      time: 'Just now',
      messages: messages || []
    };
    setChats(prev => [newChat, ...prev]);
    console.log('New chat created:', newChat);
  };

  const updateChat = (id: number, updates: Partial<Chat>) => {
    setChats(prev => prev.map(chat => 
      chat.id === id ? { ...chat, ...updates } : chat
    ));
  };

  const deleteChat = (id: number) => {
    setChats(prev => prev.filter(chat => chat.id !== id));
    if (currentChatId === id) {
      setCurrentChatId(null);
    }
  };

  const bookmarkChat = (id: number) => {
    setChats(prev => prev.map(chat => 
      chat.id === id ? { ...chat, isBookmarked: !chat.isBookmarked } : chat
    ));
  };

  const getChats = () => chats;

  const getChat = (id: number) => {
    return chats.find(chat => chat.id === id);
  };

  const value = {
    chats,
    addChat,
    updateChat,
    deleteChat,
    bookmarkChat,
    getChats,
    getChat,
    setCurrentChatId,
    currentChatId
  };

  return (
    <ChatsContext.Provider value={value}>
      {children}
    </ChatsContext.Provider>
  );
}; 