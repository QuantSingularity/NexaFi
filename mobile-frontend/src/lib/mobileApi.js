// Mobile-optimized API configuration and utilities
const API_BASE_URL = "http://localhost:5000/api/v1"; // API Gateway (all routes under /api/v1)

class MobileApiClient {
  constructor() {
    this.baseURL = API_BASE_URL;
    this.token = localStorage.getItem("access_token");
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem("access_token", token);
    } else {
      localStorage.removeItem("access_token");
    }
  }

  getHeaders() {
    const headers = {
      "Content-Type": "application/json",
    };

    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }

    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    const config = {
      headers: this.getHeaders(),
      signal: controller.signal,
      ...options,
    };

    try {
      const response = await fetch(url, config);
      clearTimeout(timeoutId);

      if (!response.ok) {
        if (response.status === 401) {
          this.setToken(null);
          window.location.href = "/auth";
          throw new Error("Unauthorized");
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === "AbortError") {
        throw new Error("Request timed out");
      }
      console.error("API request failed:", error);
      throw error;
    }
  }

  // Authentication endpoints
  async login(credentials) {
    const response = await this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
    const token = response?.token || response?.access_token;
    if (token) {
      this.setToken(token);
    }
    return response;
  }

  async register(userData) {
    const response = await this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify(userData),
    });
    const token = response?.token || response?.access_token;
    if (token) {
      this.setToken(token);
    }
    return response;
  }

  async logout() {
    try {
      await this.request("/auth/logout", { method: "POST" });
    } catch (error) {
      // Logging out locally must always succeed even if the server call fails.
      console.warn(
        "Logout request failed; clearing local session anyway.",
        error,
      );
    } finally {
      this.setToken(null);
    }
  }

  async refreshToken() {
    return this.request("/auth/refresh", { method: "POST" });
  }

  // User endpoints
  async getProfile() {
    return this.request("/users/profile");
  }

  async updateProfile(profileData) {
    return this.request("/users/profile", {
      method: "PUT",
      body: JSON.stringify(profileData),
    });
  }

  // Dashboard endpoints
  async getDashboardData() {
    return this.request("/dashboard");
  }

  async getFinancialSummary() {
    return this.request("/dashboard/financial-summary");
  }

  // Accounting endpoints
  async getAccounts(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/accounts${queryString ? `?${queryString}` : ""}`);
  }

  async createAccount(accountData) {
    return this.request("/accounts", {
      method: "POST",
      body: JSON.stringify(accountData),
    });
  }

  async getJournalEntries(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(
      `/journal-entries${queryString ? `?${queryString}` : ""}`,
    );
  }

  async createJournalEntry(entryData) {
    return this.request("/journal-entries", {
      method: "POST",
      body: JSON.stringify(entryData),
    });
  }

  async getFinancialReports(reportType, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(
      `/reports/${reportType}${queryString ? `?${queryString}` : ""}`,
    );
  }

  // Payment endpoints
  async getPaymentMethods() {
    return this.request("/payment-methods");
  }

  async addPaymentMethod(methodData) {
    return this.request("/payment-methods", {
      method: "POST",
      body: JSON.stringify(methodData),
    });
  }

  async getTransactions(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/transactions${queryString ? `?${queryString}` : ""}`);
  }

  async createTransaction(transactionData) {
    return this.request("/transactions", {
      method: "POST",
      body: JSON.stringify(transactionData),
    });
  }

  async getWallets() {
    return this.request("/wallets");
  }

  async createWallet(walletData) {
    return this.request("/wallets", {
      method: "POST",
      body: JSON.stringify(walletData),
    });
  }

  // AI endpoints
  async getInsights(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/insights${queryString ? `?${queryString}` : ""}`);
  }

  async getChatSessions() {
    return this.request("/chat/sessions");
  }

  async createChatSession(sessionName = "Financial Advisory") {
    return this.request("/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ session_name: sessionName }),
    });
  }

  async sendChatMessage(sessionId, message, context = { source: "payments" }) {
    return this.request(`/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message, context }),
    });
  }

  async generateInsights(params = { source: "payments" }) {
    return this.request("/insights/generate", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  async getCurrentCreditScore() {
    return this.request("/credit/scores/current");
  }

  async generatePrediction(predictionType, params = {}) {
    return this.request(`/predictions/${predictionType}`, {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  // Analytics endpoints
  async getAnalytics(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/analytics${queryString ? `?${queryString}` : ""}`);
  }

  async getKPIs() {
    return this.request("/analytics/kpis");
  }

  // Utility methods for mobile
  async checkConnectivity() {
    try {
      await this.request("/health");
      return true;
    } catch {
      return false;
    }
  }

  // Offline support
  getCachedData(key) {
    try {
      const cached = localStorage.getItem(`cache_${key}`);
      return cached ? JSON.parse(cached) : null;
    } catch {
      return null;
    }
  }

  setCachedData(key, data) {
    try {
      localStorage.setItem(`cache_${key}`, JSON.stringify(data));
    } catch (error) {
      console.warn("Failed to cache data:", error);
    }
  }

  clearCache() {
    const keys = Object.keys(localStorage);
    keys.forEach((key) => {
      if (key.startsWith("cache_")) {
        localStorage.removeItem(key);
      }
    });
  }
}

// Create and export a singleton instance
const mobileApiClient = new MobileApiClient();
export default mobileApiClient;
