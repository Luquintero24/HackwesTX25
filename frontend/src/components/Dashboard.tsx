import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';
import { KnowledgeGraph } from './KnowledgeGraph';
import { DailyReport } from './DailyReport';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Loader2, Activity, AlertTriangle, TrendingUp } from 'lucide-react';
import { parseKnowledgeGraphData, generateDailyReport, KnowledgeGraphData, DailyReportData } from '@/utils/dataParser';

export const Dashboard: React.FC = () => {
  const [graphData, setGraphData] = useState<KnowledgeGraphData | null>(null);
  const [reportData, setReportData] = useState<DailyReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const response = await fetch('/data/kg_facts.csv');
        const csvText = await response.text();
        
        Papa.parse(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const data = results.data as any[];
            
            if (data.length === 0) {
              setError('No data found in CSV file');
              setLoading(false);
              return;
            }

            // Parse knowledge graph data
            const graphData = parseKnowledgeGraphData(data);
            setGraphData(graphData);

            // Generate daily report
            const reportData = generateDailyReport(data);
            setReportData(reportData);

            setLoading(false);
          },
          error: (error) => {
            setError(`Error parsing CSV: ${error.message}`);
            setLoading(false);
          }
        });
      } catch (error) {
        setError(`Error loading data: ${error}`);
        setLoading(false);
      }
    };

    loadData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Loading risk detection data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-destructive flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Error Loading Data
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const highRiskComponents = reportData?.componentRisks.filter(c => c.severity === 'HIGH').length || 0;
  const totalComponents = reportData?.componentRisks.length || 0;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity className="h-8 w-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold text-foreground">Nodary</h1>
                <p className="text-sm text-muted-foreground">Automated monitoring and risk detection</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline" className="text-sm">
                Last Updated: {new Date().toLocaleTimeString()}
              </Badge>
            </div>
          </div>
        </div>
      </header>

      {/* Stats Overview */}
      <div className="container mx-auto px-6 py-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">High Risk Components</CardTitle>
              <AlertTriangle className="h-4 w-4 text-status-high" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-status-high">{highRiskComponents}</div>
              <p className="text-xs text-muted-foreground">Require immediate attention</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Components</CardTitle>
              <TrendingUp className="h-4 w-4 text-industrial-blue" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-foreground">{totalComponents}</div>
              <p className="text-xs text-muted-foreground">Under monitoring</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">System Status</CardTitle>
              <Activity className="h-4 w-4 text-status-medium" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-status-medium">Active</div>
              <p className="text-xs text-muted-foreground">Real-time monitoring</p>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <Tabs defaultValue="graph" className="space-y-6">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="graph">Knowledge Graph</TabsTrigger>
            <TabsTrigger value="report">Daily Report</TabsTrigger>
          </TabsList>

          <TabsContent value="graph" className="space-y-4">
            {graphData && (
              <KnowledgeGraph 
                data={graphData} 
                width={1200} 
                height={700}
              />
            )}
          </TabsContent>

          <TabsContent value="report" className="space-y-4">
            {reportData && <DailyReport data={reportData} />}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};