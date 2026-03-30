import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "../lib/api";

// Mock fetch
global.fetch = vi.fn();

describe("API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe("Authentication", () => {
    it("should login successfully", async () => {
      const mockResponse = {
        access_token: "test-token",
        user: { id: 1, email: "test@example.com" },
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
        headers: new Headers({ "content-type": "application/json" }),
      });

      const result = await apiClient.login({
        email: "test@example.com",
        password: "password",
      });

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/auth/login"),
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    it("should handle login failure", async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        json: async () => ({ error: "Invalid credentials" }),
      });

      await expect(
        apiClient.login({
          email: "test@example.com",
          password: "wrong",
        }),
      ).rejects.toThrow();
    });
  });

  describe("Ledger Operations", () => {
    it("should fetch accounts", async () => {
      const mockAccounts = {
        accounts: [{ id: 1, name: "Cash", type: "asset" }],
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAccounts,
        headers: new Headers({ "content-type": "application/json" }),
      });

      const result = await apiClient.getAccounts();
      expect(result).toEqual(mockAccounts);
    });
  });

  describe("Token Management", () => {
    it("should set and retrieve token", () => {
      apiClient.setToken("test-token");
      expect(localStorage.getItem("access_token")).toBe("test-token");
    });

    it("should remove token", () => {
      apiClient.setToken("test-token");
      apiClient.setToken(null);
      expect(localStorage.getItem("access_token")).toBeNull();
    });
  });
});
