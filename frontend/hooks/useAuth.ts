import { useState, useEffect } from 'react';
import { getAccessToken } from '@/lib/api/auth';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      const token = await getAccessToken();
      setIsAuthenticated(!!token);
    };

    checkAuth();
  }, []);

  return { isAuthenticated };
}
