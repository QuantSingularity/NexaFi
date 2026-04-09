import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import { Toaster } from "@/components/ui/toaster";
import AccountingModule from "./components/AccountingModule";
import AIInsightsModule from "./components/AIInsightsModule";
import AuthPage from "./components/AuthPage";
import Dashboard from "./components/Dashboard";
import DocumentsModule from "./components/DocumentsModule";
import Homepage from "./components/Homepage";
import Layout from "./components/Layout";
import PaymentsModule from "./components/PaymentsModule";
import SettingsModule from "./components/SettingsModule";
import { AppProvider, AuthProvider, useAuth } from "./contexts/AppContext";

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/auth" replace />;
};

// Public Route Component (redirect if authenticated)
const PublicRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return !isAuthenticated ? children : <Navigate to="/dashboard" replace />;
};

// Main App Routes
const AppRoutes = () => {
  return (
    <Router>
      <Routes>
        {/* Public Routes */}
        <Route
          path="/auth"
          element={
            <PublicRoute>
              <AuthPage />
            </PublicRoute>
          }
        />

        {/* Protected Routes */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Layout>
                <Dashboard />
              </Layout>
            </ProtectedRoute>
          }
        />

        <Route
          path="/accounting/*"
          element={
            <ProtectedRoute>
              <Layout>
                <AccountingModule />
              </Layout>
            </ProtectedRoute>
          }
        />

        <Route
          path="/payments/*"
          element={
            <ProtectedRoute>
              <Layout>
                <PaymentsModule />
              </Layout>
            </ProtectedRoute>
          }
        />

        <Route
          path="/ai-insights/*"
          element={
            <ProtectedRoute>
              <Layout>
                <AIInsightsModule />
              </Layout>
            </ProtectedRoute>
          }
        />

        <Route
          path="/documents/*"
          element={
            <ProtectedRoute>
              <Layout>
                <DocumentsModule />
              </Layout>
            </ProtectedRoute>
          }
        />

        <Route
          path="/settings/*"
          element={
            <ProtectedRoute>
              <Layout>
                <SettingsModule />
              </Layout>
            </ProtectedRoute>
          }
        />

        {/* Homepage */}
        <Route path="/" element={<Homepage />} />

        {/* 404 fallback */}
        <Route
          path="*"
          element={
            <div className="min-h-screen flex items-center justify-center">
              <div className="text-center">
                <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
                <p className="text-gray-600 mb-8">Page not found</p>
                <a
                  href="/dashboard"
                  className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Go to Dashboard
                </a>
              </div>
            </div>
          }
        />
      </Routes>
    </Router>
  );
};

// Main App Component
function App() {
  return (
    <AppProvider>
      <AuthProvider>
        <div className="App">
          <AppRoutes />
          <Toaster />
        </div>
      </AuthProvider>
    </AppProvider>
  );
}

export default App;
