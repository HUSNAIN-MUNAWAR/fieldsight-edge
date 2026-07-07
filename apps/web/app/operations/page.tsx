'use client';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { apiFetch, operationalContext } from '../../lib/api';

export default function OperationsPage(){
  const workspace='org-solarvista';
  const query=useQuery({queryKey:['operations',workspace],queryFn:()=>apiFetch<Record<string,any>>('/api/v1/operations/health',operationalContext(workspace))});
  const data=query.data;
  return <main className="ops-page"><header><Link href="/">← Mission control</Link><small>PLATFORM OPERATIONS · PERSISTENT DEMO</small><h1>Operations console</h1><p>Health signals are sourced from the local API, database connection, and durable queues. External providers remain clearly unconfigured boundaries.</p></header>{query.isPending?<div className="loading"><span className="spinner"/> Loading platform health…</div>:query.isError?<section className="empty-state"><h2>Health query unavailable</h2><p>{query.error.message}</p><button onClick={()=>query.refetch()}>Retry</button></section>:<section className="ops-grid"><article><label>API</label><b>{data?.api}</b><p>Request IDs and security headers enabled.</p></article><article><label>DATABASE</label><b>{data?.database?.status}</b><p>{data?.database?.dialect} local persistence · last migration {data?.last_migration}</p></article><article><label>EDGE SYNC</label><b>{data?.edge_sync?.state}</b><p>{data?.edge_sync?.pending} durable queue records awaiting reconciliation.</p></article><article><label>INFERENCE</label><b>{data?.worker?.state}</b><p>{data?.worker?.queued_inference} jobs in deterministic local workflow.</p></article><article><label>OBJECT STORAGE</label><b>{data?.object_storage?.state}</b><p>Production S3-compatible provider remains optional.</p></article><article><label>RUN MODE</label><b>{data?.mode}</b><p>No GPU, external provider, or telemetry claim is made.</p></article></section>}</main>
}
