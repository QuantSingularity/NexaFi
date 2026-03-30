import { createContext, useContext, useEffect, useReducer } from "react";
import apiClient from "../lib/api";

// Auth Context
const AuthContext = createContext();

const authReducer = (state, action) => {
  switch (action.type) {
    case "LOGIN_START":
      return { ...state, loading: true, error: null };
    case "LOGIN_SUCCESS":
      return {
        ...state,
        loading: false,
        isAuthenticated: true,
        user: action.payload.user,
        token: action.payload.token,
        error: null,
      };
    case "LOGIN_FAILURE":
      return {
        ...state,
        loading: false,
        isAuthenticated: false,
        user: null,
        token: null,
        error: action.payload,
      };
    case "LOGOUT":
      return {
        ...state,
        isAuthenticated: false,
        user: null,
        token: null,
        error: null,
      };
    case "UPDATE_USER":
      return { ...state, user: { ...state.user, ...action.payload } };
    case "CLEAR_ERROR":
      return { ...state, error: null };
    default:
      return state;
  }
};

const initialState = {
  isAuthenticated: false,
  user: null,
  token: null,
  loading: false,
  error: null,
};

export const AuthProvider = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, initialState);

  useEffect(() => {
    // Check for existing token on app load
    const token = localStorage.getItem("access_token");
    if (token) {
      apiClient.setToken(token);
      // Verify token by fetching user profile
      apiClient
        .getUserProfile()
        .then((response) => {
          dispatch({
            type: "LOGIN_SUCCESS",
            payload: { user: response.user, token },
          });
        })
        .catch(() => {
          // Token is invalid, remove it
          localStorage.removeItem("access_token");
          apiClient.setToken(null);
        });
    }
  }, []);

  const login = async (credentials) => {
    dispatch({ type: "LOGIN_START" });
    try {
      const response = await apiClient.login(credentials);
      const { access_token, user } = response;

      apiClient.setToken(access_token);
      dispatch({
        type: "LOGIN_SUCCESS",
        payload: { user, token: access_token },
      });

      return response;
    } catch (error) {
      dispatch({
        type: "LOGIN_FAILURE",
        payload: error.message,
      });
      throw error;
    }
  };

  const register = async (userData) => {
    dispatch({ type: "LOGIN_START" });
    try {
      const response = await apiClient.register(userData);
      const { access_token, user } = response;

      apiClient.setToken(access_token);
      dispatch({
        type: "LOGIN_SUCCESS",
        payload: { user, token: access_token },
      });

      return response;
    } catch (error) {
      dispatch({
        type: "LOGIN_FAILURE",
        payload: error.message,
      });
      throw error;
    }
  };

  const logout = async () => {
    try {
      await apiClient.logout();
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      apiClient.setToken(null);
      dispatch({ type: "LOGOUT" });
    }
  };

  const updateUser = (userData) => {
    dispatch({ type: "UPDATE_USER", payload: userData });
  };

  const clearError = () => {
    dispatch({ type: "CLEAR_ERROR" });
  };

  const value = {
    ...state,
    login,
    register,
    logout,
    updateUser,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

// App Context for global state
const AppContext = createContext();

const appReducer = (state, action) => {
  switch (action.type) {
    case "SET_LOADING":
      return { ...state, loading: action.payload };
    case "SET_ERROR":
      return { ...state, error: action.payload };
    case "CLEAR_ERROR":
      return { ...state, error: null };
    case "SET_THEME":
      return { ...state, theme: action.payload };
    case "SET_SIDEBAR_OPEN":
      return { ...state, sidebarOpen: action.payload };
    case "SET_NOTIFICATIONS":
      return { ...state, notifications: action.payload };
    case "ADD_NOTIFICATION":
      return {
        ...state,
        notifications: [...state.notifications, action.payload],
      };
    case "REMOVE_NOTIFICATION":
      return {
        ...state,
        notifications: state.notifications.filter(
          (n) => n.id !== action.payload,
        ),
      };
    default:
      return state;
  }
};

const initialAppState = {
  loading: false,
  error: null,
  theme: "light",
  sidebarOpen: true,
  notifications: [],
};

export const AppProvider = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialAppState);

  const setLoading = (loading) => {
    dispatch({ type: "SET_LOADING", payload: loading });
  };

  const setError = (error) => {
    dispatch({ type: "SET_ERROR", payload: error });
  };

  const clearError = () => {
    dispatch({ type: "CLEAR_ERROR" });
  };

  const setTheme = (theme) => {
    dispatch({ type: "SET_THEME", payload: theme });
    document.documentElement.classList.toggle("dark", theme === "dark");
  };

  const setSidebarOpen = (open) => {
    dispatch({ type: "SET_SIDEBAR_OPEN", payload: open });
  };

  const addNotification = (notification) => {
    const id = Date.now().toString();
    dispatch({
      type: "ADD_NOTIFICATION",
      payload: { ...notification, id },
    });

    // Auto-remove after 5 seconds
    setTimeout(() => {
      dispatch({ type: "REMOVE_NOTIFICATION", payload: id });
    }, 5000);
  };

  const removeNotification = (id) => {
    dispatch({ type: "REMOVE_NOTIFICATION", payload: id });
  };

  const value = {
    ...state,
    setLoading,
    setError,
    clearError,
    setTheme,
    setSidebarOpen,
    addNotification,
    removeNotification,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};
