import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import MobileAccountingModule from "./components/MobileAccountingModule";
import MobileAIInsightsModule from "./components/MobileAIInsightsModule";
import MobileAuthPage from "./components/MobileAuthPage";
import MobileDashboard from "./components/MobileDashboard";
import MobileHomepage from "./components/MobileHomepage";
import MobileLayout from "./components/MobileLayout";
import MobilePaymentsModule from "./components/MobilePaymentsModule";
import MobileSettingsModule from "./components/MobileSettingsModule";
import { MobileProviders, useAuth } from "./contexts/MobileContext";
import "./App.css";

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/auth" replace />;
};

// App Routes Component
const AppRoutes = () => {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<MobileHomepage />} />
      <Route
        path="/auth"
        element={
          isAuthenticated ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <MobileAuthPage />
          )
        }
      />

      {/* Protected Routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <MobileLayout>
              <MobileDashboard />
            </MobileLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/accounting"
        element={
          <ProtectedRoute>
            <MobileLayout>
              <MobileAccountingModule />
            </MobileLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/payments"
        element={
          <ProtectedRoute>
            <MobileLayout>
              <MobilePaymentsModule />
            </MobileLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/ai-insights"
        element={
          <ProtectedRoute>
            <MobileLayout>
              <MobileAIInsightsModule />
            </MobileLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <MobileLayout>
              <MobileSettingsModule />
            </MobileLayout>
          </ProtectedRoute>
        }
      />

      {/* Catch all route */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

function App() {
  return (
    <ErrorBoundary>
      <MobileProviders>
        <Router>
          <div className="App">
            <AppRoutes />
          </div>
        </Router>
      </MobileProviders>
    </ErrorBoundary>
  );
}

export default App;
