import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import AuthPage from "../components/AuthPage";
import Homepage from "../components/Homepage";

// Mock contexts
vi.mock("../contexts/AppContext", () => ({
  useAuth: () => ({
    login: vi.fn(),
    register: vi.fn(),
    loading: false,
    error: null,
    clearError: vi.fn(),
  }),
  useApp: () => ({
    addNotification: vi.fn(),
    theme: "light",
    setTheme: vi.fn(),
  }),
}));

describe("Component Tests", () => {
  describe("AuthPage", () => {
    it("renders login form elements", () => {
      render(<AuthPage />);
      expect(
        screen.getByPlaceholderText(/enter your email/i),
      ).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText(/enter your password/i),
      ).toBeInTheDocument();
    });
  });

  describe("Homepage", () => {
    it("renders homepage content", () => {
      render(
        <BrowserRouter>
          <Homepage />
        </BrowserRouter>,
      );

      const nexafiElements = screen.getAllByText(/NexaFi/);
      expect(nexafiElements.length).toBeGreaterThan(0);
      expect(screen.getByText(/future of/i)).toBeInTheDocument();
    });

    it("has call-to-action buttons", () => {
      render(
        <BrowserRouter>
          <Homepage />
        </BrowserRouter>,
      );

      const buttons = screen.getAllByText(/get started/i);
      expect(buttons.length).toBeGreaterThan(0);
    });
  });
});
