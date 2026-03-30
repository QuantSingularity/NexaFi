// API configuration and utilities
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api/v1";
const API_TIMEOUT = import.meta.env.VITE_API_TIMEOUT || 30000;

class ApiClient {
  constructor() {
    this.baseURL = API_BASE_URL;
    this.timeout = API_TIMEOUT;
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
    const config = {
      headers: this.getHeaders(),
      ...options,
    };

    if (config.body && typeof config.body === "object") {
      config.body = JSON.stringify(config.body);
    }

    // Add timeout support
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);
    config.signal = controller.signal;

    try {
      const response = await fetch(url, config);
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.error ||
            errorData.message ||
            `HTTP ${response.status}: ${response.statusText}`,
        );
      }

      const contentType = response.headers.get("content-type");
      if (contentType?.includes("application/json")) {
        return await response.json();
      }

      return await response.text();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === "AbortError") {
        throw new Error("Request timeout");
      }
      console.error("API Request failed:", error);
      throw error;
    }
  }

  // Authentication endpoints
  async register(userData) {
    return this.request("/auth/register", {
      method: "POST",
      body: userData,
    });
  }

  async login(credentials) {
    const response = await this.request("/auth/login", {
      method: "POST",
      body: credentials,
    });

    // Store token if present in response
    if (response.access_token) {
      this.setToken(response.access_token);
    }

    return response;
  }

  async logout() {
    try {
      await this.request("/auth/logout", {
        method: "POST",
      });
    } finally {
      this.setToken(null);
    }
  }

  async refreshToken() {
    return this.request("/auth/refresh", {
      method: "POST",
    });
  }

  // User endpoints
  async getUserProfile() {
    return this.request("/users/profile");
  }

  async updateUserProfile(profileData) {
    return this.request("/users/profile", {
      method: "PUT",
      body: profileData,
    });
  }

  // Ledger endpoints
  async getAccounts() {
    return this.request("/accounts");
  }

  async createAccount(accountData) {
    return this.request("/accounts", {
      method: "POST",
      body: accountData,
    });
  }

  async initializeAccounts() {
    return this.request("/accounts/initialize", {
      method: "POST",
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
      body: entryData,
    });
  }

  async getTrialBalance(asOfDate) {
    const params = asOfDate ? `?as_of_date=${asOfDate}` : "";
    return this.request(`/reports/trial-balance${params}`);
  }

  async getBalanceSheet(asOfDate) {
    const params = asOfDate ? `?as_of_date=${asOfDate}` : "";
    return this.request(`/reports/balance-sheet${params}`);
  }

  async getIncomeStatement(startDate, endDate) {
    return this.request(
      `/reports/income-statement?start_date=${startDate}&end_date=${endDate}`,
    );
  }

  // Payment endpoints
  async getPaymentMethods() {
    return this.request("/payment-methods");
  }

  async createPaymentMethod(methodData) {
    return this.request("/payment-methods", {
      method: "POST",
      body: methodData,
    });
  }

  async getTransactions(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/transactions${queryString ? `?${queryString}` : ""}`);
  }

  async createTransaction(transactionData) {
    return this.request("/transactions", {
      method: "POST",
      body: transactionData,
    });
  }

  async getWallets() {
    return this.request("/wallets");
  }

  async getWallet(currency) {
    return this.request(`/wallets/${currency}`);
  }

  async getPaymentAnalytics(startDate, endDate) {
    return this.request(
      `/analytics/summary?start_date=${startDate}&end_date=${endDate}`,
    );
  }

  // AI endpoints
  async predictCashFlow(data) {
    return this.request("/predictions/cash-flow", {
      method: "POST",
      body: data,
    });
  }

  async predictCreditScore(data) {
    return this.request("/predictions/credit-score", {
      method: "POST",
      body: data,
    });
  }

  async getInsights(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/insights${queryString ? `?${queryString}` : ""}`);
  }

  async generateInsights(data) {
    return this.request("/insights/generate", {
      method: "POST",
      body: data,
    });
  }

  async markInsightRead(insightId) {
    return this.request(`/insights/${insightId}/read`, {
      method: "POST",
    });
  }

  async getChatSessions() {
    return this.request("/chat/sessions");
  }

  async createChatSession(sessionData) {
    return this.request("/chat/sessions", {
      method: "POST",
      body: sessionData,
    });
  }

  async getChatMessages(sessionId) {
    return this.request(`/chat/sessions/${sessionId}/messages`);
  }

  async sendChatMessage(sessionId, messageData) {
    return this.request(`/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body: messageData,
    });
  }

  // Health check
  async healthCheck() {
    return this.request("/health");
  }
}

// Create singleton instance
const apiClient = new ApiClient();

export default apiClient;
