import { motion } from "framer-motion";
import {
  AlertTriangle,
  BarChart3,
  Bot,
  Brain,
  CheckCircle,
  Eye,
  Lightbulb,
  LineChart,
  MessageSquare,
  Send,
  Star,
  Target,
  ThumbsDown,
  ThumbsUp,
  TrendingUp,
  User,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp, useAuth } from "../contexts/AppContext";
import apiClient from "../lib/api";

const toCashFlowView = (result) => ({
  total: result.summary.total_predicted_cash_flow,
  average: result.summary.average_daily_cash_flow,
  method: result.summary.method,
  historyDays: result.summary.history_days,
  confidenceLevel: result.summary.confidence_level,
  skill: result.metrics.skill_vs_seasonal_naive,
  warnings: result.warnings || [],
  series: result.forecast.map((point) => ({
    date: point.date.slice(5),
    predicted: point.predicted_cash_flow,
    lower: point.confidence_interval.lower,
    upper: point.confidence_interval.upper,
  })),
});

const toCreditView = (score) => {
  const details = score.calculation_details || {};
  return {
    score: score.score,
    riskCategory: details.risk_category,
    method: details.method,
    decision: details.decision,
    factors: details.recommendations || [],
    inputs: score.input_features || {},
  };
};

const severityLabel = (severity) =>
  ({ critical: "high", warning: "medium" })[severity] || "low";

const money = (value) =>
  Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });

const AIInsightsModule = () => {
  const { addNotification } = useApp();
  // eslint-disable-next-line no-unused-vars -- surfaced during UI modernization
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("insights");
  // eslint-disable-next-line no-unused-vars -- fetched data surfaced during UI modernization
  const [insights, setInsights] = useState([]);
  const [predictions, setPredictions] = useState({});
  // eslint-disable-next-line no-unused-vars -- fetched data surfaced during UI modernization
  const [chatSessions, setChatSessions] = useState([]);
  const [activeChatSession, setActiveChatSession] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [horizonDays, setHorizonDays] = useState("30");

  const loadAIData = useCallback(async () => {
    try {
      setLoading(true);

      const [insightsResponse, sessionsResponse] = await Promise.all([
        apiClient.getInsights({ per_page: 10 }),
        apiClient.getChatSessions(),
      ]);
      setInsights(insightsResponse.insights || []);
      setChatSessions(sessionsResponse.sessions || []);

      const [cashFlow, credit] = await Promise.allSettled([
        apiClient.predictCashFlow({ source: "payments", days_ahead: 30 }),
        apiClient.getCurrentCreditScore(),
      ]);
      const next = {};
      if (cashFlow.status === "fulfilled") {
        next.cashFlow = toCashFlowView(cashFlow.value);
      } else {
        next.cashFlowError = cashFlow.reason?.message || "Forecast unavailable";
      }
      if (credit.status === "fulfilled") {
        next.creditScore = toCreditView(credit.value);
      }
      setPredictions(next);
    } catch (error) {
      console.error("Failed to load AI data:", error);
      addNotification({
        type: "error",
        title: "Error",
        message: "Failed to load AI insights",
      });
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  useEffect(() => {
    loadAIData();
    // Load once on mount. Depending on loadAIData would re-fire the effect
    // whenever the addNotification identity changes and loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runCashFlow = async (days) => {
    try {
      const result = await apiClient.predictCashFlow({
        source: "payments",
        days_ahead: days,
      });
      setPredictions((prev) => ({
        ...prev,
        cashFlow: toCashFlowView(result),
        cashFlowError: null,
      }));
    } catch (error) {
      setPredictions((prev) => ({ ...prev, cashFlowError: error.message }));
      addNotification({
        type: "error",
        title: "Forecast failed",
        message: error.message,
      });
    }
  };

  const refreshCredit = async () => {
    const inputs = predictions.creditScore?.inputs;
    if (!inputs || Object.keys(inputs).length === 0) {
      addNotification({
        type: "info",
        title: "Business details needed",
        message: "Submit business details in Credit to generate a score",
      });
      return;
    }
    try {
      const score = await apiClient.calculateCreditScore(inputs);
      setPredictions((prev) => ({ ...prev, creditScore: toCreditView(score) }));
    } catch (error) {
      addNotification({
        type: "error",
        title: "Credit analysis failed",
        message: error.message,
      });
    }
  };

  const generateInsights = async () => {
    try {
      const result = await apiClient.generateInsights({ source: "payments" });
      const fresh = result.insights || [];
      setInsights((prev) => [...fresh, ...prev]);
      addNotification({
        type: "success",
        title: "Insights updated",
        message: fresh.length
          ? `${fresh.length} new insights`
          : "Nothing notable found in your recent activity",
      });
    } catch (error) {
      addNotification({
        type: "error",
        title: "Could not generate insights",
        message: error.message,
      });
    }
  };

  const InsightsOverview = () => {
    const displayInsights = insights.map((item) => ({
      id: item.id,
      title: item.title,
      description: item.description,
      type: item.insight_type,
      severity: severityLabel(item.severity),
      created_at: item.created_at,
      is_read: item.is_read,
    }));

    const getInsightIcon = (type) => {
      switch (type) {
        case "opportunity":
          return <Target className="w-5 h-5 text-green-600" />;
        case "alert":
          return <AlertTriangle className="w-5 h-5 text-red-600" />;
        case "recommendation":
          return <Lightbulb className="w-5 h-5 text-blue-600" />;
        case "risk":
          return <AlertTriangle className="w-5 h-5 text-orange-600" />;
        default:
          return <Brain className="w-5 h-5 text-purple-600" />;
      }
    };

    const getSeverityColor = (severity) => {
      switch (severity) {
        case "high":
          return "bg-red-100 text-red-800";
        case "medium":
          return "bg-yellow-100 text-yellow-800";
        case "low":
          return "bg-green-100 text-green-800";
        default:
          return "bg-gray-100 text-gray-800";
      }
    };

    return (
      <div className="space-y-6">
        {/* AI Performance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Insights Generated
                  </p>
                  <p className="text-2xl font-bold text-gray-900">247</p>
                  <div className="flex items-center mt-2 text-sm text-green-600">
                    <TrendingUp className="w-4 h-4 mr-1" />
                    +23% this month
                  </div>
                </div>
                <div className="p-3 rounded-full bg-purple-100">
                  <Brain className="w-6 h-6 text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Prediction Accuracy
                  </p>
                  <p className="text-2xl font-bold text-gray-900">87.5%</p>
                  <div className="flex items-center mt-2 text-sm text-green-600">
                    <TrendingUp className="w-4 h-4 mr-1" />
                    +2.1% improvement
                  </div>
                </div>
                <div className="p-3 rounded-full bg-blue-100">
                  <Target className="w-6 h-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Actions Taken
                  </p>
                  <p className="text-2xl font-bold text-gray-900">156</p>
                  <div className="flex items-center mt-2 text-sm text-blue-600">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    63% implementation rate
                  </div>
                </div>
                <div className="p-3 rounded-full bg-green-100">
                  <Zap className="w-6 h-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Insights */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Brain className="w-5 h-5 text-purple-600" />
              <span>Recent AI Insights</span>
            </CardTitle>
            <CardDescription>
              AI-powered recommendations and alerts for your business
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {displayInsights.length === 0 && (
                <div className="text-sm text-gray-600 py-6 text-center">
                  No insights yet.
                  <Button className="ml-3" size="sm" onClick={generateInsights}>
                    Analyze my activity
                  </Button>
                </div>
              )}
              {displayInsights.map((insight) => (
                <motion.div
                  key={insight.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`p-4 border rounded-lg hover:shadow-md transition-shadow ${
                    !insight.is_read ? "bg-blue-50 border-blue-200" : "bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3 flex-1">
                      {getInsightIcon(insight.type)}
                      <div className="flex-1">
                        <div className="flex items-center space-x-2 mb-2">
                          <h4 className="font-medium text-gray-900">
                            {insight.title}
                          </h4>
                          {!insight.is_read && (
                            <Badge className="bg-blue-100 text-blue-800">
                              New
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 mb-3">
                          {insight.description}
                        </p>
                        <div className="flex items-center space-x-4 text-xs text-gray-500">
                          <Badge className={getSeverityColor(insight.severity)}>
                            {insight.severity} priority
                          </Badge>
                          <span>
                            {new Date(insight.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <Button variant="ghost" size="sm">
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <ThumbsUp className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <ThumbsDown className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  const PredictionsTab = () => {
    const cashFlow = predictions.cashFlow;
    const cashFlowData = cashFlow?.series || [];

    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Cash Flow Prediction */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <LineChart className="w-5 h-5 text-blue-600" />
                <span>Cash Flow Forecast</span>
              </CardTitle>
              <CardDescription>
                AI-powered 6-month cash flow prediction
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-600">
                      Projected net cash flow, next 30 days
                    </p>
                    <p className="text-2xl font-bold text-blue-600">
                      {cashFlow ? `$${money(cashFlow.total)}` : "No forecast"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-600">Interval</p>
                    <p className="text-lg font-bold text-green-600">
                      {cashFlow
                        ? `${(cashFlow.confidenceLevel * 100).toFixed(0)}%`
                        : "n/a"}
                    </p>
                  </div>
                </div>
                {!cashFlow && (
                  <p className="text-sm text-gray-600">
                    {predictions.cashFlowError ||
                      "Not enough transaction history to forecast yet."}
                  </p>
                )}

                <ResponsiveContainer width="100%" height={200}>
                  <RechartsLineChart data={cashFlowData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip
                      formatter={(value) => [
                        `$${value.toLocaleString()}`,
                        "Predicted",
                      ]}
                    />
                    <Line
                      type="monotone"
                      dataKey="predicted"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                    />
                  </RechartsLineChart>
                </ResponsiveContainer>

                <div className="space-y-2">
                  <p className="text-sm font-medium text-gray-700">
                    Model details:
                  </p>
                  {(cashFlow
                    ? [
                        `Method: ${cashFlow.method.replace("_", " ")}`,
                        `Based on ${cashFlow.historyDays} days of history`,
                        ...cashFlow.warnings,
                      ]
                    : []
                  ).map((factor, index) => (
                    <div
                      key={index}
                      className="flex items-center space-x-2 text-sm text-gray-600"
                    >
                      <CheckCircle className="w-3 h-3 text-green-500" />
                      <span>{factor}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Credit Score Prediction */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Star className="w-5 h-5 text-yellow-600" />
                <span>Credit Score Analysis</span>
              </CardTitle>
              <CardDescription>
                Current score and improvement recommendations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="text-center">
                  <div className="relative w-32 h-32 mx-auto">
                    <svg
                      className="w-32 h-32 transform -rotate-90"
                      viewBox="0 0 36 36"
                    >
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="#e5e7eb"
                        strokeWidth="2"
                      />
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="#3b82f6"
                        strokeWidth="2"
                        strokeDasharray={`${((predictions.creditScore?.score || 0) / 850) * 100}, 100`}
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-gray-900">
                          {predictions.creditScore?.score ?? "n/a"}
                        </div>
                        <div className="text-xs text-gray-500">
                          Credit Score
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4">
                    {predictions.creditScore?.riskCategory ? (
                      <Badge className="bg-blue-100 text-blue-800">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        {predictions.creditScore.riskCategory.replace("_", " ")}
                      </Badge>
                    ) : (
                      <span className="text-xs text-gray-500">
                        {predictions.creditScore
                          ? "Scored with fallback rules"
                          : "No credit score yet"}
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium text-gray-700">
                    Improvement Factors:
                  </p>
                  {(predictions.creditScore?.factors || []).map(
                    (factor, index) => (
                      <div
                        key={index}
                        className="flex items-center space-x-2 text-sm text-gray-600"
                      >
                        <CheckCircle className="w-3 h-3 text-green-500" />
                        <span>{factor}</span>
                      </div>
                    ),
                  )}
                </div>

                <Button className="w-full" onClick={refreshCredit}>
                  Recalculate Score
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Prediction Controls */}
        <Card>
          <CardHeader>
            <CardTitle>Generate New Predictions</CardTitle>
            <CardDescription>
              Create custom predictions based on your specific scenarios
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <h4 className="font-medium">Cash Flow Prediction</h4>
                <div className="space-y-3">
                  <div>
                    <Label htmlFor="timeframe">Prediction Timeframe</Label>
                    <Select value={horizonDays} onValueChange={setHorizonDays}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select timeframe" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="30">30 days</SelectItem>
                        <SelectItem value="90">90 days</SelectItem>
                        <SelectItem value="180">180 days</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button
                    className="w-full"
                    onClick={() => runCashFlow(Number(horizonDays))}
                  >
                    <BarChart3 className="w-4 h-4 mr-2" />
                    Generate Cash Flow Forecast
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Credit Score Analysis</h4>
                <div className="space-y-3">
                  <Button className="w-full" onClick={refreshCredit}>
                    <Star className="w-4 h-4 mr-2" />
                    Analyze Credit Score
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  const ChatTab = () => {
    const [newMessage, setNewMessage] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const scrollRef = useRef(null);

    const initialMessages = [
      {
        id: 1,
        content:
          "Hello! I'm your AI financial advisor. How can I help you today?",
        sender: "ai",
        timestamp: new Date().toISOString(),
      },
    ];

    const displayMessages =
      chatMessages.length > 0 ? chatMessages : initialMessages;

    useEffect(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }, [displayMessages, isTyping]);

    const sendMessage = async () => {
      if (!newMessage.trim()) return;

      const userMessage = {
        id: Date.now(),
        content: newMessage,
        sender: "user",
        timestamp: new Date().toISOString(),
      };

      setChatMessages((prev) => {
        const base = prev.length === 0 ? initialMessages : prev;
        return [...base, userMessage];
      });
      const messageText = newMessage;
      setNewMessage("");
      setIsTyping(true);

      try {
        let sessionId = activeChatSession;
        if (!sessionId) {
          const sessionRes = await apiClient.createChatSession({
            session_name: "Financial Advisory",
          });
          sessionId = sessionRes.session?.id || sessionRes.id;
          setActiveChatSession(sessionId);
        }
        const res = await apiClient.sendChatMessage(sessionId, {
          message: messageText,
          context: { source: "payments" },
        });
        const aiContent =
          res.assistant_message?.content ||
          res.reply?.content ||
          "No response was returned.";
        setChatMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            content: aiContent,
            sender: "ai",
            timestamp: new Date().toISOString(),
          },
        ]);
      } catch (error) {
        setChatMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            content: `The advisor is unavailable right now: ${error.message}`,
            sender: "ai",
            timestamp: new Date().toISOString(),
          },
        ]);
      } finally {
        setIsTyping(false);
      }
    };

    return (
      <div className="space-y-6">
        <Card className="h-96">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <MessageSquare className="w-5 h-5 text-blue-600" />
              <span>AI Financial Advisor</span>
            </CardTitle>
            <CardDescription>
              Chat with your AI advisor for personalized financial insights
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col h-full">
            <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
              <div className="space-y-4">
                {displayMessages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                        message.sender === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-900"
                      }`}
                    >
                      <div className="flex items-start space-x-2">
                        {message.sender === "ai" && (
                          <Bot className="w-4 h-4 mt-1 text-blue-600" />
                        )}
                        {message.sender === "user" && (
                          <User className="w-4 h-4 mt-1 text-white" />
                        )}
                        <div>
                          <p className="text-sm">{message.content}</p>
                          <p
                            className={`text-xs mt-1 ${
                              message.sender === "user"
                                ? "text-blue-100"
                                : "text-gray-500"
                            }`}
                          >
                            {new Date(message.timestamp).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {isTyping && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 text-gray-900 px-4 py-2 rounded-lg">
                      <div className="flex items-center space-x-2">
                        <Bot className="w-4 h-4 text-blue-600" />
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div
                            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                            style={{ animationDelay: "0.1s" }}
                          ></div>
                          <div
                            className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                            style={{ animationDelay: "0.2s" }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>

            <div className="flex space-x-2 mt-4">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Ask me about your finances..."
                onKeyPress={(e) => e.key === "Enter" && sendMessage()}
                className="flex-1"
              />
              <Button
                onClick={sendMessage}
                disabled={!newMessage.trim() || isTyping}
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Questions</CardTitle>
            <CardDescription>
              Common questions you can ask your AI advisor
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                "What's my cash flow forecast for next month?",
                "How can I improve my profit margins?",
                "Which expenses should I prioritize cutting?",
                "What are my best performing revenue streams?",
                "How does my business compare to industry benchmarks?",
                "What tax optimization strategies do you recommend?",
              ].map((question, index) => (
                <Button
                  key={index}
                  variant="outline"
                  className="text-left h-auto p-4 justify-start"
                  onClick={() => setNewMessage(question)}
                >
                  <MessageSquare className="w-4 h-4 mr-2 flex-shrink-0" />
                  <span className="text-sm">{question}</span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">AI Insights</h1>
        <p className="text-gray-600 mt-1">
          AI-powered financial analysis, predictions, and advisory
        </p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-6"
      >
        <TabsList>
          <TabsTrigger value="insights">Insights</TabsTrigger>
          <TabsTrigger value="predictions">Predictions</TabsTrigger>
          <TabsTrigger value="chat">AI Advisor</TabsTrigger>
        </TabsList>

        <TabsContent value="insights">
          <InsightsOverview />
        </TabsContent>

        <TabsContent value="predictions">
          <PredictionsTab />
        </TabsContent>

        <TabsContent value="chat">
          <ChatTab />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AIInsightsModule;
