import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { jwtDecode } from 'jwt-decode';

interface JwtPayload {
  exp?: number;
  sub?: string;
}

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  username: string | null;
  login: (token: string) => void;
  logout: () => void;
  resetInactivityTimer: () => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

const TOKEN_KEY = 'token';
const INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000;
const LAST_ACTIVITY_KEY = 'lastActivity';

function readUsername(token: string | null): string | null {
  if (!token) return null;
  try {
    const decoded = jwtDecode<JwtPayload>(token);
    return decoded.sub ?? null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const jwtTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LAST_ACTIVITY_KEY);
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = null;
    }
    if (jwtTimerRef.current) {
      clearTimeout(jwtTimerRef.current);
      jwtTimerRef.current = null;
    }
    setToken(null);
    window.location.href = '/login';
  }, []);

  const resetInactivityTimer = useCallback(() => {
    if (!token) return;
    localStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
    }
    inactivityTimerRef.current = setTimeout(() => {
      console.log('无操作超时，自动登出');
      logout();
    }, INACTIVITY_TIMEOUT_MS);
  }, [token, logout]);

  const login = useCallback((newToken: string) => {
    localStorage.setItem(TOKEN_KEY, newToken);
    localStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
    setToken(newToken);
  }, []);

  // JWT 过期硬上限 + 无操作超时
  useEffect(() => {
    if (!token) return;

    let decoded: JwtPayload;
    try {
      decoded = jwtDecode<JwtPayload>(token);
    } catch {
      logout();
      return;
    }

    // JWT exp 硬上限
    if (decoded.exp) {
      const jwtDelay = decoded.exp * 1000 - Date.now();
      if (jwtDelay <= 0) {
        logout();
        return;
      }
      if (jwtTimerRef.current) clearTimeout(jwtTimerRef.current);
      jwtTimerRef.current = setTimeout(() => {
        console.log('JWT 过期，自动登出');
        logout();
      }, jwtDelay);
    }

    // 无操作超时：检查上次活动时间
    const lastActivity = localStorage.getItem(LAST_ACTIVITY_KEY);
    if (lastActivity) {
      const elapsed = Date.now() - Number(lastActivity);
      if (elapsed >= INACTIVITY_TIMEOUT_MS) {
        logout();
        return;
      }
    }

    // 启动无操作计时器
    resetInactivityTimer();

    return () => {
      if (inactivityTimerRef.current) {
        clearTimeout(inactivityTimerRef.current);
        inactivityTimerRef.current = null;
      }
      if (jwtTimerRef.current) {
        clearTimeout(jwtTimerRef.current);
        jwtTimerRef.current = null;
      }
    };
  }, [token]);

  // 监听用户交互事件（鼠标、键盘、触摸、滚动），重置无操作计时器
  useEffect(() => {
    if (!token) return;

    const events = ['mousedown', 'keydown', 'touchstart', 'scroll', 'click'] as const;
    const handler = () => resetInactivityTimer();

    events.forEach((e) => window.addEventListener(e, handler, { passive: true }));
    return () => {
      events.forEach((e) => window.removeEventListener(e, handler));
    };
  }, [token, resetInactivityTimer]);

  return (
    <AuthContext.Provider
      value={{
        token,
        isAuthenticated: !!token,
        username: readUsername(token),
        login,
        logout,
        resetInactivityTimer,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) throw new Error('useAuth 必须在 AuthProvider 内使用');
  return ctx;
}
