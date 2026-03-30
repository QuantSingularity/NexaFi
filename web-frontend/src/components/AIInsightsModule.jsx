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
import { useEffect, useState } from "react";
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

const AIInsightsModule = () => {
  const { addNotification } = useApp();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("insights");
  const [_insights, setInsights] = useState([]);
  const [predictions, setPredictions] = useState({});
  const [_chatSessions, setChatSessions] = useState([]);
  const [_activeChatSession, _setActiveChatSession] = useState(null);
  const [_chatMessages, setChatMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAIData();
  }, [loadAIData]);

  const loadAIData = async () => {
    try {
      setLoading(true);

      // Load insights
      const insightsResponse = await apiClient.getInsights({ per_page: 10 });
      setInsights(insightsResponse.insights || []);

      // Load chat sessions
      const sessionsResponse = await apiClient.getChatSessions();
      setChatSessions(sessionsResponse.sessions || []);

      // Generate mock predictions
      const mockPredictions = {
        cashFlow: {
          prediction: 15000,
          confidence: 0.85,
          trend: "positive",
          factors: [
            "Seasonal increase",
            "New client contracts",
            "Reduced expenses",
          ],
        },
        creditScore: {
          score: 750,
          change: +15,
          factors: [
            "Improved payment history",
            "Lower credit utilization",
            "Account age",
          ],
        },
      };
      setPredictions(mockPredictions);
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
  };

  const InsightsOverview = () => {
    const mockInsights = [
      {
        id: 1,
        title: "Cash Flow Optimization",
        description:
          "Your cash flow could improve by 15% by adjusting payment terms with 3 key clients.",
        type: "opportunity",
        severity: "medium",
        impact: "high",
        confidence: 0.87,
        created_at: "2024-06-10T10:00:00Z",
        is_read: false,
      },
      {
        id: 2,
        title: "Expense Anomaly Detected",
        description:
          "Marketing expenses are 40% higher than usual this month. Review recent campaigns.",
        type: "alert",
        severity: "high",
        impact: "medium",
        confidence: 0.92,
        created_at: "2024-06-09T15:30:00Z",
        is_read: false,
      },
      {
        id: 3,
        title: "Revenue Growth Opportunity",
        description:
          "Based on seasonal patterns, consider launching a promotion in the next 2 weeks.",
        type: "recommendation",
        severity: "low",
        impact: "high",
        confidence: 0.78,
        created_at: "2024-06-08T09:15:00Z",
        is_read: true,
      },
      {
        id: 4,
        title: "Payment Risk Assessment",
        description:
          "Client ABC Corp has delayed payments. Consider adjusting credit terms.",
        type: "risk",
        severity: "medium",
        impact: "medium",
        confidence: 0.83,
        created_at: "2024-06-07T14:20:00Z",
        is_read: true,
      },
    ];

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
              {mockInsights.map((insight) => (
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
                          <span>
                            Confidence: {(insight.confidence * 100).toFixed(0)}%
                          </span>
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
    const mockCashFlowData = [
      { month: "Jul", predicted: 18000, actual: null },
      { month: "Aug", predicted: 22000, actual: null },
      { month: "Sep", predicted: 19000, actual: null },
      { month: "Oct", predicted: 25000, actual: null },
      { month: "Nov", predicted: 21000, actual: null },
      { month: "Dec", predicted: 28000, actual: null },
    ];

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
                      Next Month Prediction
                    </p>
                    <p className="text-2xl font-bold text-blue-600">
                      $
                      {predictions.cashFlow?.prediction?.toLocaleString() ||
                        "15,000"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-600">Confidence</p>
                    <p className="text-lg font-bold text-green-600">
                      {(
                        (predictions.cashFlow?.confidence || 0.85) * 100
                      ).toFixed(0)}
                      %
                    </p>
                  </div>
                </div>

                <ResponsiveContainer width="100%" height={200}>
                  <RechartsLineChart data={mockCashFlowData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
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
                    Key Factors:
                  </p>
                  {(predictions.cashFlow?.factors || []).map(
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
                        strokeDasharray={`${((predictions.creditScore?.score || 750) / 850) * 100}, 100`}
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-gray-900">
                          {predictions.creditScore?.score || 750}
                        </div>
                        <div className="text-xs text-gray-500">
                          Credit Score
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4">
                    <Badge className="bg-green-100 text-green-800">
                      <TrendingUp className="w-3 h-3 mr-1" />+
                      {predictions.creditScore?.change || 15} this month
                    </Badge>
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

                <Button className="w-full">Generate Detailed Report</Button>
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
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Select timeframe" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="3months">3 Months</SelectItem>
                        <SelectItem value="6months">6 Months</SelectItem>
                        <SelectItem value="12months">12 Months</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button className="w-full">
                    <BarChart3 className="w-4 h-4 mr-2" />
                    Generate Cash Flow Forecast
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Credit Score Analysis</h4>
                <div className="space-y-3">
                  <div>
                    <Label htmlFor="scenario">Scenario Type</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Select scenario" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="current">
                          Current Trajectory
                        </SelectItem>
                        <SelectItem value="optimistic">
                          Optimistic Scenario
                        </SelectItem>
                        <SelectItem value="conservative">
                          Conservative Scenario
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button className="w-full">
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

    const mockMessages = [
      {
        id: 1,
        content:
          "Hello! I'm your AI financial advisor. How can I help you today?",
        sender: "ai",
        timestamp: "2024-06-10T10:00:00Z",
      },
      {
        id: 2,
        content:
          "I'd like to understand my cash flow trends for the past quarter.",
        sender: "user",
        timestamp: "2024-06-10T10:01:00Z",
      },
      {
        id: 3,
        content:
          "Based on your financial data, your cash flow has shown a positive trend over the past quarter. Your average monthly cash flow increased by 15%, primarily driven by improved collection times and new client acquisitions. Would you like me to break down the specific factors contributing to this improvement?",
        sender: "ai",
        timestamp: "2024-06-10T10:02:00Z",
      },
      {
        id: 4,
        content:
          "Yes, please provide more details about the collection times improvement.",
        sender: "user",
        timestamp: "2024-06-10T10:03:00Z",
      },
    ];

    const sendMessage = async () => {
      if (!newMessage.trim()) return;

      const userMessage = {
        id: Date.now(),
        content: newMessage,
        sender: "user",
        timestamp: new Date().toISOString(),
      };

      // Add user message
      setChatMessages((prev) => [...prev, userMessage]);
      setNewMessage("");
      setIsTyping(true);

      // Simulate AI response
      setTimeout(() => {
        const aiResponse = {
          id: Date.now() + 1,
          content:
            "I understand your question. Let me analyze your data and provide you with detailed insights...",
          sender: "ai",
          timestamp: new Date().toISOString(),
        };
        setChatMessages((prev) => [...prev, aiResponse]);
        setIsTyping(false);
      }, 2000);
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
            <ScrollArea className="flex-1 pr-4">
              <div className="space-y-4">
                {mockMessages.map((message) => (
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
