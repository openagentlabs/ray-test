import LZString from 'lz-string';

// IndexedDB helper for large data storage
const DB_NAME = 'midas_documentation_db';
const DB_VERSION = 1;
const STORE_NAME = 'documentation_data';

interface StorageResult {
  success: boolean;
  error?: string;
  usedIndexedDB?: boolean;
}

/**
 * Initialize IndexedDB
 */
const initIndexedDB = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
  });
};

/**
 * Store data in IndexedDB
 */
const storeInIndexedDB = async (key: string, data: string): Promise<StorageResult> => {
  try {
    const db = await initIndexedDB();
    return new Promise((resolve) => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.put(data, key);

      request.onsuccess = () => {
        resolve({ success: true, usedIndexedDB: true });
      };

      request.onerror = () => {
        resolve({ success: false, error: request.error?.message, usedIndexedDB: true });
      };
    });
  } catch (error: any) {
    return { success: false, error: error?.message, usedIndexedDB: true };
  }
};

/**
 * Retrieve data from IndexedDB
 */
const getFromIndexedDB = async (key: string): Promise<string | null> => {
  try {
    const db = await initIndexedDB();
    return new Promise((resolve) => {
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(key);

      request.onsuccess = () => {
        resolve(request.result || null);
      };

      request.onerror = () => {
        resolve(null);
      };
    });
  } catch (error) {
    return null;
  }
};

/**
 * Compress data using LZString
 */
const compressData = (data: string): string => {
  try {
    return LZString.compressToUTF16(data);
  } catch (error) {
    console.error('Compression error:', error);
    return data; // Return uncompressed if compression fails
  }
};

/**
 * Decompress data using LZString
 */
const decompressData = (compressed: string): string | null => {
  try {
    return LZString.decompressFromUTF16(compressed);
  } catch (error) {
    console.error('Decompression error:', error);
    return null;
  }
};

/**
 * Get size in MB
 */
const getSizeInMB = (data: string): number => {
  return new Blob([data]).size / (1024 * 1024);
};

/**
 * Optimized storage: Use compression and IndexedDB for large data
 * Falls back to sessionStorage for smaller data or if IndexedDB fails
 */
export const optimizedSetItem = async (
  key: string,
  data: string,
  thresholdMB: number = 2
): Promise<StorageResult> => {
  const sizeMB = getSizeInMB(data);
  
  // Compress data
  const compressed = compressData(data);
  const compressedSizeMB = getSizeInMB(compressed);
  
  console.log(`📦 Storage optimization for ${key}:`);
  console.log(`   Original size: ${sizeMB.toFixed(2)}MB`);
  console.log(`   Compressed size: ${compressedSizeMB.toFixed(2)}MB`);
  console.log(`   Compression ratio: ${((1 - compressedSizeMB / sizeMB) * 100).toFixed(1)}%`);

  // Try sessionStorage first for smaller data
  if (compressedSizeMB < thresholdMB) {
    try {
      sessionStorage.setItem(key, compressed);
      sessionStorage.setItem(`${key}_compressed`, 'true');
      return { success: true, usedIndexedDB: false };
    } catch (error: any) {
      if (error.name === 'QuotaExceededError' || error.code === 22) {
        console.log(`   ⚠️ SessionStorage quota exceeded, trying IndexedDB...`);
        // Fall through to IndexedDB
      } else {
        return { success: false, error: error?.message, usedIndexedDB: false };
      }
    }
  }

  // Use IndexedDB for large data or when sessionStorage fails
  try {
    const result = await storeInIndexedDB(key, compressed);
    if (result.success) {
      // Store a flag in sessionStorage to indicate data is in IndexedDB
      try {
        sessionStorage.setItem(`${key}_source`, 'indexeddb');
        sessionStorage.setItem(`${key}_compressed`, 'true');
      } catch (e) {
        // Ignore if we can't store the flag
      }
    }
    return result;
  } catch (error: any) {
    return { success: false, error: error?.message, usedIndexedDB: true };
  }
};

/**
 * Optimized retrieval: Get data from IndexedDB or sessionStorage
 */
export const optimizedGetItem = async (key: string): Promise<string | null> => {
  // Check if data is in IndexedDB
  const source = sessionStorage.getItem(`${key}_source`);
  
  if (source === 'indexeddb') {
    const data = await getFromIndexedDB(key);
    if (data) {
      const isCompressed = sessionStorage.getItem(`${key}_compressed`) === 'true';
      if (isCompressed) {
        const decompressed = decompressData(data);
        if (decompressed) {
          return decompressed;
        }
      }
      return data;
    }
  }

  // Try sessionStorage
  const data = sessionStorage.getItem(key);
  if (data) {
    const isCompressed = sessionStorage.getItem(`${key}_compressed`) === 'true';
    if (isCompressed) {
      const decompressed = decompressData(data);
      if (decompressed) {
        return decompressed;
      }
    }
    return data;
  }

  return null;
};

/**
 * Clear optimized storage
 */
export const optimizedRemoveItem = async (key: string): Promise<void> => {
  // Remove from IndexedDB
  try {
    const db = await initIndexedDB();
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    store.delete(key);
  } catch (error) {
    // Ignore errors
  }

  // Remove from sessionStorage
  try {
    sessionStorage.removeItem(key);
    sessionStorage.removeItem(`${key}_source`);
    sessionStorage.removeItem(`${key}_compressed`);
  } catch (error) {
    // Ignore errors
  }
};