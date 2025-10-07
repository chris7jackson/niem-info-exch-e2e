import axios, { AxiosInstance } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEV_TOKEN = 'devtoken'; // In production, this would come from environment or auth

export interface Schema {
  schema_id: string;
  filename: string;
  primary_filename?: string;
  all_filenames?: string[];
  uploaded_at: string;
  active: boolean;
}

export interface ValidationError {
  file: string;
  line?: number;
  column?: number;
  message: string;
  severity: string;
  rule?: string;
  context?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  summary: string;
  raw_output?: string;
}

export interface IngestFileResult {
  filename: string;
  status: string;
  nodes_created?: number;
  relationships_created?: number;
  error?: string;
  validation_details?: ValidationResult;
}

export interface IngestResponse {
  schema_id: string;
  files_processed: number;
  total_nodes_created: number;
  total_relationships_created: number;
  results: IngestFileResult[];
}

// Direct execution returns IngestResponse immediately
export type IngestResult = IngestResponse;

export interface Neo4jStats {
  nodes: number;
  relationships: number;
  indexes: number;
  constraints: number;
}

export interface UploadedFile {
  original_name: string;
  stored_name: string;
  size: number;
  last_modified: string | null;
  content_type: string;
}

// Schema Graph Types
export interface GraphNode {
  id: string;
  label: string;
  namespace: string;
  namespaceURI: string;
  namespaceCategory: string; // Data-driven - not an enum
  nodeType: string; // Data-driven - not an enum
  documentation?: string;
  hasChildren: boolean;
  depth: number;
  metadata: {
    [key: string]: any; // Flexible metadata based on nodeType
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  edgeType: string; // Data-driven - not an enum
  cardinality?: string;
  documentation?: string;
}

export interface Namespace {
  id: string;
  prefix: string;
  uri: string;
  category: string; // Data-driven - not an enum
  label: string;
  documentation?: string;
  classCount: number;
  propertyCount: number;
}

export interface GraphMetadata {
  schemaId: string;
  totalNodes: number;
  totalEdges: number;
  namespaceCount: number;
  parseDate: string;
  cmfVersion: string;
}

export interface SchemaGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  namespaces: Namespace[];
  metadata: GraphMetadata;
}

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Authorization': `Bearer ${DEV_TOKEN}`,
      },
    });
  }

  // Schema Management
  async uploadSchema(files: File[], filePaths: string[], skipNiemNdr: boolean = false): Promise<any> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    // Send file paths as JSON array
    formData.append('file_paths', JSON.stringify(filePaths));
    formData.append('skip_niem_ndr', skipNiemNdr.toString());

    const response = await this.client.post('/api/schema/xsd', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async getSchemas(): Promise<Schema[]> {
    const response = await this.client.get('/api/schema');
    return response.data;
  }

  async activateSchema(schemaId: string): Promise<any> {
    const response = await this.client.post(`/api/schema/activate/${schemaId}`);
    return response.data;
  }

  async getSchemaGraph(schemaId: string): Promise<SchemaGraph> {
    const response = await this.client.get(`/api/schema/${schemaId}/graph`);
    return response.data;
  }

  // Data Ingestion - Direct to Neo4j
  async ingestXml(files: File[]): Promise<IngestResult> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await this.client.post('/api/ingest/xml', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async ingestJson(files: File[]): Promise<IngestResult> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await this.client.post('/api/ingest/json', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  // Neo4j Administration
  async getNeo4jStats(): Promise<Neo4jStats> {
    const response = await this.client.get('/api/admin/neo4j/stats');
    return response.data.stats;
  }

  async clearNeo4jData(): Promise<any> {
    const response = await this.client.post('/api/admin/neo4j/clear-data');
    return response.data;
  }

  async clearNeo4jSchema(): Promise<any> {
    const response = await this.client.post('/api/admin/neo4j/clear-schema');
    return response.data;
  }

  async clearNeo4jAll(): Promise<any> {
    const response = await this.client.post('/api/admin/neo4j/clear-all');
    return response.data;
  }


  // Graph Schema Management
  async configureGraphSchema(): Promise<any> {
    const response = await this.client.post('/api/admin/graph-schema/configure');
    return response.data;
  }

  async getGraphSchemaInfo(): Promise<any> {
    const response = await this.client.get('/api/admin/graph-schema/info');
    return response.data;
  }

  // System Reset
  async resetSystem(options: {
    schemas?: boolean;
    data?: boolean;
    neo4j?: boolean;
    dry_run?: boolean;
    confirm_token?: string;
  }): Promise<any> {
    const response = await this.client.post('/api/admin/reset', options);
    return response.data;
  }

  // Get uploaded files
  async getUploadedFiles(): Promise<UploadedFile[]> {
    const response = await this.client.get('/api/ingest/files');
    return response.data.files;
  }
}

export const apiClient = new ApiClient();
export default apiClient;