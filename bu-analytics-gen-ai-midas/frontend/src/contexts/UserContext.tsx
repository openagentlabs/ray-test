import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import authService from '../services/authService';

export interface User {
  name: string;
  role: string;
  avatar: string;
  email?: string;
  id?: string;
  username?: string;
}

interface UserContextType {
  user: User | null;
  setUser: (user: User) => void;
  updateUserName: (name: string) => void;
  isAuthenticated: boolean;
  login: (userData: User) => void;
  logout: () => void;
}

interface UserProviderProps {
  children: ReactNode;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export const useUser = () => {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
};

export const UserProvider: React.FC<UserProviderProps> = ({ children }) => {
  const [user, setUserState] = useState<User | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Initialize authentication state on app start
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const { isAuthenticated, user: authUser } = await authService.initializeAuth();
        
        if (isAuthenticated && authUser) {
          // Convert API user to frontend user format
          const frontendUser: User = {
            name: authUser.full_name,
            role: 'Data Analyst', // Default role
            avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(authUser.full_name)}&background=3b82f6&color=ffffff`,
            email: authUser.email || '',
            id: authUser.id.toString(),
            username: authUser.username
          };
          setUserState(frontendUser);
        } else {
          setUserState(null);
        }
      } catch (error) {
        console.error('Error initializing authentication:', error);
        setUserState(null);
      } finally {
        setIsInitialized(true);
      }
    };

    initializeAuth();
  }, []);

  useEffect(() => {
    const onAuthChanged = () => {
      if (!authService.isAuthenticated()) {
        setUserState(null);
      }
    };
    window.addEventListener('midas:auth-changed', onAuthChanged);
    return () => window.removeEventListener('midas:auth-changed', onAuthChanged);
  }, []);

  const setUser = (userData: User) => {
    setUserState(userData);
    // Save to localStorage for persistence
    localStorage.setItem('userData', JSON.stringify(userData));
  };

  const updateUserName = (name: string) => {
    if (user) {
      const updatedUser = { ...user, name };
      setUserState(updatedUser);
      localStorage.setItem('userData', JSON.stringify(updatedUser));
    }
  };

  const login = (userData: User) => {
    setUserState(userData);
    localStorage.setItem('userData', JSON.stringify(userData));
  };

  const logout = () => {
    setUserState(null);
    void authService.logoutFromServer().finally(() => {
      authService.logout();
    });
  };

  const isAuthenticated = user !== null;

  const value: UserContextType = {
    user,
    setUser,
    updateUserName,
    isAuthenticated,
    login,
    logout
  };

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}; 