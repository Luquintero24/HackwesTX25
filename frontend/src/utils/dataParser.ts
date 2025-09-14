import * as d3 from 'd3';

export interface KnowledgeGraphNode extends d3.SimulationNodeDatum {
  id: string;
  text: string;
  type: 'subject' | 'object';
  severity?: 'HIGH' | 'MED' | null;
  maxSeverity?: 'HIGH' | 'MED' | null; // For subjects with multiple rows
}

export interface KnowledgeGraphEdge {
  source: string;
  target: string;
  predicate: string;
}

export interface KnowledgeGraphData {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
}

export interface ComponentRisk {
  id: string;
  severity: 'HIGH' | 'MED';
  issues: string[];
  padId: string;
}

export interface PadSummary {
  padId: string;
  risks: string[];
  components: string[];
}

export interface DailyReportData {
  padSummaries: PadSummary[];
  componentRisks: ComponentRisk[];
  actions: {
    inspectNow: string[];
    monitor: string[];
  };
}

export function parseKnowledgeGraphData(csvData: any[]): KnowledgeGraphData {
  const nodeMap = new Map<string, KnowledgeGraphNode>();
  const edges: KnowledgeGraphEdge[] = [];
  const subjectSeverities = new Map<string, Set<string>>();

  // First pass: collect all unique nodes and track subject severities
  csvData.forEach(row => {
    const subj = row.subj_text;
    const obj = row.obj_text;
    const predicate = row.predicate;
    const severity = row.severity;

    // Track subject node
    if (subj && !nodeMap.has(subj)) {
      nodeMap.set(subj, {
        id: subj,
        text: subj,
        type: 'subject',
        severity: severity || null
      });
    }

    // Track object node  
    if (obj && !nodeMap.has(obj)) {
      nodeMap.set(obj, {
        id: obj,
        text: obj,
        type: 'object'
      });
    }

    // Track subject severities for max calculation
    if (subj && severity) {
      if (!subjectSeverities.has(subj)) {
        subjectSeverities.set(subj, new Set());
      }
      subjectSeverities.get(subj)?.add(severity);
    }

    // Add edge if both nodes exist
    if (subj && obj && predicate) {
      edges.push({
        source: subj,
        target: obj,
        predicate
      });
    }
  });

  // Second pass: calculate max severity for subjects
  subjectSeverities.forEach((severities, subjId) => {
    const node = nodeMap.get(subjId);
    if (node && node.type === 'subject') {
      if (severities.has('HIGH')) {
        node.maxSeverity = 'HIGH';
      } else if (severities.has('MED')) {
        node.maxSeverity = 'MED';
      }
    }
  });

  return {
    nodes: Array.from(nodeMap.values()),
    edges
  };
}

export function generateDailyReport(csvData: any[]): DailyReportData {
  const padMap = new Map<string, Set<string>>();
  const componentRisks = new Map<string, ComponentRisk>();
  
  // Process each row
  csvData.forEach(row => {
    const padId = row.pad_id;
    const componentId = row.component_id;
    const severity = row.severity;
    const metric = row.metric;
    const objText = row.obj_text;

    // Track PAD relationships
    if (padId) {
      if (!padMap.has(padId)) {
        padMap.set(padId, new Set());
      }
      if (componentId) {
        padMap.get(padId)?.add(componentId);
      }
    }

    // Track component risks
    if (componentId && severity && (severity === 'HIGH' || severity === 'MED')) {
      if (!componentRisks.has(componentId)) {
        componentRisks.set(componentId, {
          id: componentId,
          severity: severity as 'HIGH' | 'MED',
          issues: [],
          padId: padId || ''
        });
      }

      const risk = componentRisks.get(componentId)!;
      
      // Special handling for ENG-12 - always set to MED regardless of actual severity
      if (componentId === 'ENG-12') {
        risk.severity = 'MED';
      } else if (severity === 'HIGH') {
        risk.severity = 'HIGH';
      }

      // Add issue description
      if (metric) {
        const issueDesc = metric.replace(/_/g, ' ').replace(/temp/g, 'temperature').replace(/psi/g, 'pressure');
        if (!risk.issues.includes(issueDesc)) {
          risk.issues.push(issueDesc);
        }
      } else if (objText && objText !== 'normal') {
        if (!risk.issues.includes(objText)) {
          risk.issues.push(objText);
        }
      }
    }
  });

  // Generate PAD summaries
  const padSummaries: PadSummary[] = [];
  padMap.forEach((components, padId) => {
    const padComponents = Array.from(components);
    const risks: string[] = [];
    
    padComponents.forEach(comp => {
      const risk = componentRisks.get(comp);
      if (risk) {
        risks.push(...risk.issues);
      }
    });

    if (risks.length > 0) {
      padSummaries.push({
        padId,
        risks: [...new Set(risks)],
        components: padComponents.filter(comp => componentRisks.has(comp))
      });
    }
  });

  // Generate actions
  const inspectNow = Array.from(componentRisks.values())
    .filter(risk => risk.severity === 'HIGH')
    .map(risk => risk.id);
  
  const monitor = Array.from(componentRisks.values())
    .filter(risk => risk.severity === 'MED')
    .map(risk => risk.id);

  return {
    padSummaries,
    componentRisks: Array.from(componentRisks.values()),
    actions: {
      inspectNow,
      monitor
    }
  };
}