import { useEffect } from 'react';
import { useRouter } from 'expo-router';
import { logoutApi } from '@/lib/api/auth';

export default function Logout() {
  const router = useRouter();

  useEffect(() => {
    const performLogout = async () => {
      await logoutApi();
      router.replace('/login');
    };

    performLogout();
  }, [router]);

  return null;
}
