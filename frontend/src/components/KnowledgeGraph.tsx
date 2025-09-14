import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { KnowledgeGraphData, KnowledgeGraphNode, KnowledgeGraphEdge } from '@/utils/dataParser';

interface KnowledgeGraphProps {
  data: KnowledgeGraphData;
  width?: number;
  height?: number;
}

export const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({ 
  data, 
  width = 1000, 
  height = 600 
}) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    // Clear previous render
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current);
    const container = svg.append("g");

    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        container.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Create simulation
    const simulation = d3.forceSimulation<KnowledgeGraphNode>(data.nodes)
      .force("link", d3.forceLink<KnowledgeGraphNode, KnowledgeGraphEdge>(data.edges)
        .id(d => d.id)
        .distance(150))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(30));

    // Create links
    const link = container.append("g")
      .attr("class", "links")
      .selectAll("line")
      .data(data.edges)
      .enter().append("line")
      .attr("stroke", "hsl(var(--graph-edge))")
      .attr("stroke-width", 2)
      .attr("stroke-opacity", 0.6);

    // Create link labels
    const linkLabel = container.append("g")
      .attr("class", "link-labels")
      .selectAll("text")
      .data(data.edges)
      .enter().append("text")
      .attr("font-size", "10px")
      .attr("fill", "hsl(var(--muted-foreground))")
      .attr("text-anchor", "middle")
      .text(d => d.predicate.replace(/_/g, " "));

    // Create nodes
    const node = container.append("g")
      .attr("class", "nodes")
      .selectAll("circle")
      .data(data.nodes)
      .enter().append("circle")
      .attr("r", 20)
      .attr("fill", d => {
        // Special color overrides
        if (d.id === 'PAD-A') return "hsl(var(--status-special-purple))";
        if (d.id === 'ENG-12') return "hsl(var(--status-special-orange))";
        
        if (d.type === 'subject') {
          if (d.maxSeverity === 'HIGH') return "hsl(var(--status-high))";
          if (d.maxSeverity === 'MED') return "hsl(var(--status-medium))";
          return "hsl(var(--status-low))";
        }
        return "hsl(var(--status-unknown))";
      })
      .attr("stroke", "hsl(var(--card))")
      .attr("stroke-width", 2)
      .style("cursor", "pointer");

    // Create node labels
    const nodeLabel = container.append("g")
      .attr("class", "node-labels")
      .selectAll("text")
      .data(data.nodes)
      .enter().append("text")
      .attr("font-size", "12px")
      .attr("font-weight", "500")
      .attr("fill", "hsl(var(--foreground))")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .style("pointer-events", "none")
      .text(d => d.text);

    // Add drag behavior
    const drag = d3.drag<SVGCircleElement, KnowledgeGraphNode>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    node.call(drag);

    // Add hover effects
    node
      .on("mouseover", function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr("r", 25)
          .attr("stroke-width", 3);
      })
      .on("mouseout", function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr("r", 20)
          .attr("stroke-width", 2);
      });

    // Update positions on simulation tick
    simulation.on("tick", () => {
      link
        .attr("x1", d => (d.source as any).x)
        .attr("y1", d => (d.source as any).y)
        .attr("x2", d => (d.target as any).x)
        .attr("y2", d => (d.target as any).y);

      linkLabel
        .attr("x", d => ((d.source as any).x + (d.target as any).x) / 2)
        .attr("y", d => ((d.source as any).y + (d.target as any).y) / 2);

      node
        .attr("cx", d => d.x!)
        .attr("cy", d => d.y!);

      nodeLabel
        .attr("x", d => d.x!)
        .attr("y", d => d.y!);
    });

    // Clean up
    return () => {
      simulation.stop();
    };
  }, [data, width, height]);

  return (
    <div className="w-full bg-graph-bg border border-border rounded-lg overflow-hidden">
      <div className="p-4 border-b border-border bg-card">
        <h3 className="text-lg font-semibold text-foreground">Knowledge Graph</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Interactive visualization of system relationships. Drag to move nodes, scroll to zoom.
        </p>
        <div className="flex gap-4 mt-3 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-status-high"></div>
            <span className="text-muted-foreground">High Risk</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-status-medium"></div>
            <span className="text-muted-foreground">Medium Risk</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-status-low"></div>
            <span className="text-muted-foreground">Normal</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-status-unknown"></div>
            <span className="text-muted-foreground">Other Nodes</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-status-special-purple"></div>
            <span className="text-muted-foreground">PAD-A (Special)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-status-special-orange"></div>
            <span className="text-muted-foreground">ENG-12 (Special)</span>
          </div>
        </div>
      </div>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="w-full"
        style={{ minHeight: '600px' }}
      />
    </div>
  );
};