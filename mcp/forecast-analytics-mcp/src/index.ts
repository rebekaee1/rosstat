import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const baseUrl = process.env.FORECAST_ANALYTICS_API_URL || 'http://127.0.0.1:8000/api/v1/analytics';
const token = process.env.FORECAST_ANALYTICS_API_TOKEN || '';

async function api(path: string, init: RequestInit = {}) {
  if (!token) {
    throw new Error('Missing FORECAST_ANALYTICS_API_TOKEN');
  }
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Analytics-Token': token,
      ...(init.headers || {}),
    },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`Analytics API ${response.status}: ${JSON.stringify(payload)}`);
  }
  return payload;
}

function text(data: unknown) {
  return { content: [{ type: 'text' as const, text: JSON.stringify(data, null, 2) }] };
}

const server = new McpServer({
  name: 'forecast-analytics-mcp',
  version: '0.1.0',
});

server.registerTool(
  'analytics_status',
  {
    title: 'Analytics status',
    description: 'Get Forecast Analytics OS sync health, lag and recent runs.',
    inputSchema: {},
  },
  async () => text(await api('/health')),
);

server.registerTool(
  'page_performance_deep_dive',
  {
    title: 'Page performance deep dive',
    description: 'List top page performance from the analytics warehouse.',
    inputSchema: {
      limit: z.number().int().min(1).max(500).default(50),
    },
  },
  async ({ limit }) => text(await api(`/pages?limit=${limit}`)),
);

server.registerTool(
  'search_query_cluster_analysis',
  {
    title: 'Search query cluster analysis',
    description: 'List search phrases and landing pages for clustering and opportunity analysis.',
    inputSchema: {
      limit: z.number().int().min(1).max(500).default(100),
    },
  },
  async ({ limit }) => text(await api(`/search-phrases?limit=${limit}`)),
);

server.registerTool(
  'detect_anomalies',
  {
    title: 'Detect anomalies',
    description: 'Return page opportunities and anomaly candidates with evidence.',
    inputSchema: {},
  },
  async () => text(await api('/anomalies')),
);

server.registerTool(
  'compare_deploy_impact',
  {
    title: 'Compare deploy impact',
    description: 'Return recent sync/deploy impact evidence available in the analytics warehouse.',
    inputSchema: {},
  },
  async () => text(await api('/deploy-impact')),
);

server.registerTool(
  'metrika_stat_query',
  {
    title: 'Metrika stat query',
    description: 'Run a controlled Yandex Metrika Reporting API query through Forecast Analytics API.',
    inputSchema: {
      counter_id: z.string().default('107136069'),
      report_type: z.string().default('data'),
      metrics: z.array(z.string()).min(1),
      dimensions: z.array(z.string()).default([]),
      date_from: z.string().optional(),
      date_to: z.string().optional(),
      filters: z.string().optional(),
      limit: z.number().int().min(1).max(500).default(100),
    },
  },
  async (payload) => text(await api('/query/metrika', { method: 'POST', body: JSON.stringify(payload) })),
);

server.registerTool(
  'propose_analytics_action',
  {
    title: 'Propose analytics action',
    description: 'Create an audited action proposal; does not apply external changes.',
    inputSchema: {
      action_type: z.string(),
      target: z.record(z.unknown()).default({}),
      payload: z.record(z.unknown()).default({}),
      diff: z.record(z.unknown()).optional(),
      reason: z.string().optional(),
    },
  },
  async (payload) => text(await api('/actions/propose', { method: 'POST', body: JSON.stringify(payload) })),
);

const transport = new StdioServerTransport();
await server.connect(transport);
