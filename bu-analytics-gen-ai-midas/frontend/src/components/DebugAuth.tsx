import React from 'react';
import { useUser } from '../contexts/UserContext';

const DebugAuth: React.FC = () => {
  const { user, isAuthenticated } = useUser();

  return (
    <div style={{ 
      position: 'fixed', 
      top: '10px', 
      right: '10px', 
      background: 'rgba(0,0,0,0.8)', 
      color: 'white', 
      padding: '10px', 
      borderRadius: '5px',
      fontSize: '12px',
      zIndex: 9999
    }}>
      <div>Auth: {isAuthenticated ? 'YES' : 'NO'}</div>
      <div>User: {user ? user.name : 'NULL'}</div>
      <div>LocalStorage: {localStorage.getItem('userData') ? 'Has Data' : 'Empty'}</div>
    </div>
  );
};

export default DebugAuth; 