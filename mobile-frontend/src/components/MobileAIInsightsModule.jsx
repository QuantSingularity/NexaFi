import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  BarChart3,
  Brain,
  CheckCircle,
  Lightbulb,
  Loader2,
  MessageCircle,
  RefreshCw,
  Send,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp, useAuth } from "../contexts/MobileContext";
import mobileApiClient from "../lib/mobileApi";

const MobileAIInsightsModule = () => {
  const { user } = useAuth();
  const { addNotification, isOnline } = useApp();
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [sendingMessage, setSendingMessage] = useState(false);
  const [activeSession, setActiveSession] = useState(null);
  const [refreshingInsights, setRefreshingInsights] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    scrollToBottom();
  }, [scrollToBottom]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadData = async () => {
    try {
      setLoading(true);

      const [insightsData, sessionsData] = await Promise.all([
        mobileApiClient.getInsights().catch(() => ({ insights: [] })),
        mobileApiClient.getChatSessions().catch(() => ({ sessions: [] })),
      ]);

      setInsights(insightsData.insights || insightsData || []);

      if (sessionsData.sessions && sessionsData.sessions.length > 0) {
        const session = sessionsData.sessions[0];
        setActiveSession(session);
        if (session.messages) {
          setChatMessages(session.messages);
        }
      } else {
        await createNewSession();
      }

      loadPredictions();
    } catch (error) {
      console.error("Failed to load AI data:", error);
      addNotification({
        type: "error",
        message: "Failed to load AI insights",
      });
    } finally {
      setLoading(false);
    }
  };

  const createNewSession = async () => {
    try {
      const welcomeMessage = {
        role: "assistant",
        content:
          "Hello! I'm your AI financial assistant. I can help you with financial analysis, predictions, and recommendations. How can I assist you today?",
        timestamp: new Date().toISOString(),
      };
      setChatMessages([welcomeMessage]);
    } catch (error) {
      console.error("Failed to create session:", error);
    }
  };

  const loadPredictions = async () => {
    try {
      const cashFlowPrediction = await mobileApiClient
        .generatePrediction("cash-flow", {
          period: "30d",
        })
        .catch(() => null);

      const revenuePrediction = await mobileApiClient
        .generatePrediction("revenue", {
          period: "90d",
        })
        .catch(() => null);

      const predictionsData = [];

      if (cashFlowPrediction) {
        predictionsData.push({
          type: "cash_flow",
          title: "Cash Flow Forecast",
          description: "30-day cash flow prediction",
          value: cashFlowPrediction.predicted_value,
          confidence: cashFlowPrediction.confidence,
          trend: cashFlowPrediction.trend,
        });
      }

      if (revenuePrediction) {
        predictionsData.push({
          type: "revenue",
          title: "Revenue Projection",
          description: "90-day revenue forecast",
          value: revenuePrediction.predicted_value,
          confidence: revenuePrediction.confidence,
          trend: revenuePrediction.trend,
        });
      }

      setPredictions(predictionsData);
    } catch (error) {
      console.error("Failed to load predictions:", error);
    }
  };

  const handleSendMessage = async () => {
    if (!currentMessage.trim() || sendingMessage || !isOnline) {
      return;
    }

    const userMessage = {
      role: "user",
      content: currentMessage.trim(),
      timestamp: new Date().toISOString(),
    };

    setChatMessages((prev) => [...prev, userMessage]);
    setCurrentMessage("");
    setSendingMessage(true);

    try {
      const sessionId = activeSession?.id || "default";
      const response = await mobileApiClient.sendChatMessage(
        sessionId,
        currentMessage.trim(),
      );

      const assistantMessage = {
        role: "assistant",
        content:
          response.message ||
          response.response ||
          "I understand. Let me help you with that.",
        timestamp: new Date().toISOString(),
      };

      setChatMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Failed to send message:", error);

      const errorMessage = {
        role: "assistant",
        content:
          "I apologize, but I'm having trouble connecting right now. Please try again in a moment.",
        timestamp: new Date().toISOString(),
        error: true,
      };

      setChatMessages((prev) => [...prev, errorMessage]);

      addNotification({
        type: "error",
        message: "Failed to send message",
      });
    } finally {
      setSendingMessage(false);
    }
  };

  const handleRefreshInsights = async () => {
    try {
      setRefreshingInsights(true);
      const insightsData = await mobileApiClient.getInsights({
        refresh: true,
      });
      setInsights(insightsData.insights || insightsData || []);
      addNotification({
        type: "success",
        message: "Insights refreshed successfully",
      });
    } catch (error) {
      console.error("Failed to refresh insights:", error);
      addNotification({
        type: "error",
        message: "Failed to refresh insights",
      });
    } finally {
      setRefreshingInsights(false);
    }
  };

  const getInsightIcon = (type) => {
    switch (type) {
      case "opportunity":
        return <Lightbulb className="h-5 w-5 text-yellow-600" />;
      case "warning":
        return <AlertCircle className="h-5 w-5 text-red-600" />;
      case "success":
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case "trend":
        return <TrendingUp className="h-5 w-5 text-blue-600" />;
      default:
        return <Sparkles className="h-5 w-5 text-purple-600" />;
    }
  };

  const getInsightColor = (type) => {
    switch (type) {
      case "opportunity":
        return "bg-yellow-100 border-yellow-300";
      case "warning":
        return "bg-red-100 border-red-300";
      case "success":
        return "bg-green-100 border-green-300";
      case "trend":
        return "bg-blue-100 border-blue-300";
      default:
        return "bg-purple-100 border-purple-300";
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="bg-gradient-to-br from-purple-600 to-purple-700 text-white p-6 rounded-b-3xl">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-2"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white/20 rounded-xl">
                <Brain className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">AI Insights</h1>
                <p className="text-purple-100 text-sm">
                  Powered by advanced machine learning
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Main Content */}
      <div className="p-4 space-y-4">
        <Tabs defaultValue="insights" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="insights">Insights</TabsTrigger>
            <TabsTrigger value="predictions">Predictions</TabsTrigger>
            <TabsTrigger value="chat">AI Chat</TabsTrigger>
          </TabsList>

          <TabsContent value="insights" className="space-y-4">
            <div className="flex justify-between items-center">
              <p className="text-sm text-gray-600">
                {insights.length} insights available
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefreshInsights}
                disabled={refreshingInsights || !isOnline}
              >
                <RefreshCw
                  className={`h-4 w-4 mr-2 ${refreshingInsights ? "animate-spin" : ""}`}
                />
                Refresh
              </Button>
            </div>

            <div className="space-y-3">
              <AnimatePresence>
                {insights.length === 0 ? (
                  <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12">
                      <Brain className="h-12 w-12 text-gray-400 mb-4" />
                      <p className="text-gray-600 text-center">
                        No insights available yet
                      </p>
                      <p className="text-sm text-gray-400 text-center mt-2">
                        Keep using NexaFi and AI will generate personalized
                        insights
                      </p>
                    </CardContent>
                  </Card>
                ) : (
                  insights.map((insight, index) => (
                    <motion.div
                      key={insight.id || index}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 20 }}
                      transition={{ delay: index * 0.1 }}
                    >
                      <Card
                        className={`border-l-4 ${getInsightColor(insight.type)}`}
                      >
                        <CardContent className="p-4">
                          <div className="flex gap-3">
                            <div className="flex-shrink-0">
                              {getInsightIcon(insight.type)}
                            </div>
                            <div className="flex-1">
                              <h3 className="font-semibold text-sm mb-1">
                                {insight.title}
                              </h3>
                              <p className="text-sm text-gray-600 mb-2">
                                {insight.description}
                              </p>
                              {insight.recommendation && (
                                <div className="bg-white rounded-lg p-3 border">
                                  <p className="text-sm font-medium mb-1">
                                    Recommendation:
                                  </p>
                                  <p className="text-sm text-gray-600">
                                    {insight.recommendation}
                                  </p>
                                </div>
                              )}
                              {insight.impact && (
                                <div className="mt-2 flex items-center gap-2">
                                  <Badge variant="secondary">
                                    Impact: {insight.impact}
                                  </Badge>
                                  {insight.confidence && (
                                    <Badge variant="outline">
                                      {insight.confidence}% confident
                                    </Badge>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))
                )}
              </AnimatePresence>
            </div>
          </TabsContent>

          <TabsContent value="predictions" className="space-y-4">
            <div className="space-y-3">
              {predictions.length === 0 ? (
                <Card>
                  <CardContent className="flex flex-col items-center justify-center py-12">
                    <Target className="h-12 w-12 text-gray-400 mb-4" />
                    <p className="text-gray-600 text-center">
                      No predictions available
                    </p>
                    <p className="text-sm text-gray-400 text-center mt-2">
                      Predictions will be generated based on your financial data
                    </p>
                  </CardContent>
                </Card>
              ) : (
                predictions.map((prediction, index) => (
                  <motion.div
                    key={prediction.type}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-lg flex items-center gap-2">
                          <BarChart3 className="h-5 w-5 text-blue-600" />
                          {prediction.title}
                        </CardTitle>
                        <CardDescription>
                          {prediction.description}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="flex items-baseline gap-2">
                          <span className="text-3xl font-bold">
                            {formatCurrency(prediction.value)}
                          </span>
                          {prediction.trend && (
                            <Badge
                              className={
                                prediction.trend === "up"
                                  ? "bg-green-100 text-green-700"
                                  : "bg-red-100 text-red-700"
                              }
                            >
                              {prediction.trend === "up" ? (
                                <TrendingUp className="h-3 w-3 mr-1" />
                              ) : (
                                <TrendingDown className="h-3 w-3 mr-1" />
                              )}
                              {prediction.trend}
                            </Badge>
                          )}
                        </div>

                        {prediction.confidence && (
                          <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                              <span className="text-gray-600">Confidence</span>
                              <span className="font-medium">
                                {prediction.confidence}%
                              </span>
                            </div>
                            <Progress value={prediction.confidence} />
                          </div>
                        )}

                        <div className="bg-blue-50 rounded-lg p-3">
                          <p className="text-sm text-blue-900">
                            Based on historical data and current trends, this
                            prediction has a {prediction.confidence}% confidence
                            level.
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))
              )}
            </div>
          </TabsContent>

          <TabsContent value="chat" className="space-y-4">
            <Card className="h-[calc(100vh-280px)] flex flex-col">
              <CardHeader className="border-b">
                <CardTitle className="text-lg flex items-center gap-2">
                  <MessageCircle className="h-5 w-5 text-purple-600" />
                  AI Financial Assistant
                </CardTitle>
                <CardDescription>
                  Ask me anything about your finances
                </CardDescription>
              </CardHeader>

              <ScrollArea className="flex-1 p-4">
                <div className="space-y-4">
                  {chatMessages.map((message, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                          message.role === "user"
                            ? "bg-blue-600 text-white"
                            : message.error
                              ? "bg-red-100 text-red-900 border border-red-200"
                              : "bg-gray-100 text-gray-900"
                        }`}
                      >
                        <p className="text-sm whitespace-pre-wrap">
                          {message.content}
                        </p>
                        <p
                          className={`text-xs mt-1 ${
                            message.role === "user"
                              ? "text-blue-200"
                              : "text-gray-500"
                          }`}
                        >
                          {message.timestamp
                            ? new Date(message.timestamp).toLocaleTimeString()
                            : ""}
                        </p>
                      </div>
                    </motion.div>
                  ))}
                  {sendingMessage && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 rounded-2xl px-4 py-3">
                        <div className="flex gap-2">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                          <div
                            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                            style={{ animationDelay: "0.1s" }}
                          />
                          <div
                            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                            style={{ animationDelay: "0.2s" }}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              </ScrollArea>

              <div className="border-t p-4">
                <div className="flex gap-2">
                  <Input
                    placeholder="Ask me about your finances..."
                    value={currentMessage}
                    onChange={(e) => setCurrentMessage(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    disabled={sendingMessage || !isOnline}
                  />
                  <Button
                    onClick={handleSendMessage}
                    disabled={
                      !currentMessage.trim() || sendingMessage || !isOnline
                    }
                  >
                    {sendingMessage ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {!isOnline && (
                  <p className="text-xs text-red-600 mt-2">
                    You're offline. Chat will be available when you reconnect.
                  </p>
                )}
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default MobileAIInsightsModule;
