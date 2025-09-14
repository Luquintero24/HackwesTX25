import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { DailyReportData } from '@/utils/dataParser';

interface DailyReportProps {
  data: DailyReportData;
}

export const DailyReport: React.FC<DailyReportProps> = ({ data }) => {
  const formatIssues = (issues: string[]) => {
    return issues.map(issue => 
      issue.replace(/_/g, ' ')
           .replace(/temp/g, 'temperature')
           .replace(/psi/g, 'pressure')
           .replace(/pct/g, 'percentage')
    ).join(', ');
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-6 w-6 text-industrial-warning" />
        <h2 className="text-2xl font-bold text-foreground">Daily Risk Report</h2>
        <Badge variant="outline" className="ml-auto">
          {new Date().toLocaleDateString()}
        </Badge>
      </div>

      {/* PAD Summary Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-foreground">PAD Summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.padSummaries.map(pad => (
            <div key={pad.padId} className="p-4 border border-border rounded-lg bg-muted/30">
              <div className="flex items-start justify-between mb-3">
                <h4 className="font-medium text-foreground">{pad.padId}</h4>
                <Badge variant={pad.padId === 'PAD-A' ? 'default' : 'destructive'} className={pad.padId === 'PAD-A' ? 'bg-status-medium text-white' : 'bg-status-high text-white'}>
                  {pad.padId === 'PAD-A' ? 'Medium Risk' : 'High Risk'}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-2">
                {pad.padId === 'PAD-A' ? 'Medium' : 'High'} risk of {formatIssues(pad.risks)}.
              </p>
              <div className="flex flex-wrap gap-2">
                {pad.components.map(comp => (
                  <Badge key={comp} variant="outline" className="text-xs">
                    {comp}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Component Risks Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-foreground">Component Risks</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.componentRisks.map(component => (
            <Alert key={component.id} className="border-l-4 border-l-status-high">
              <AlertTriangle className="h-4 w-4 text-status-high" />
              <AlertDescription>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <span className="font-medium text-foreground">{component.id}</span>
                    <Badge 
                      variant={component.severity === 'HIGH' ? 'destructive' : 'default'}
                      className={`ml-2 text-xs ${
                        component.severity === 'HIGH' 
                          ? 'bg-status-high text-white' 
                          : 'bg-status-medium text-white'
                      }`}
                    >
                      {component.severity} severity
                    </Badge>
              <p className="text-sm text-muted-foreground mt-1">
                {component.id === 'ENG-12' ? 'High engine oil temperature, engine water temperature, and exceeded limits detected. Requires monitoring.' : formatIssues(component.issues) + ' detected. Requires immediate inspection.'}
              </p>
                  </div>
                </div>
              </AlertDescription>
            </Alert>
          ))}
        </CardContent>
      </Card>

      {/* Actions Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-foreground">Recommended Actions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.actions.inspectNow.length > 0 && (
            <div className="p-4 border border-status-high/20 rounded-lg bg-status-high/5">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4 text-status-high" />
                <span className="font-medium text-foreground">Inspect Now</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.actions.inspectNow.map(component => (
                  <Badge key={component} className="bg-status-high text-white">
                    {component}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {data.actions.monitor.length > 0 ? (
            <div className="p-4 border border-status-medium/20 rounded-lg bg-status-medium/5">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="h-4 w-4 text-status-medium" />
                <span className="font-medium text-foreground">Monitor</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.actions.monitor.map(component => (
                  <Badge key={component} className="bg-status-medium text-white">
                    {component}
                  </Badge>
                ))}
              </div>
            </div>
          ) : (
            <div className="p-4 border border-muted rounded-lg bg-muted/30">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-status-low" />
                <span className="font-medium text-muted-foreground">Monitor: None</span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                Components with medium severity requiring monitoring.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};