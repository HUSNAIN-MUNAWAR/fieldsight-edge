'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch, operationalContext } from '../../lib/api';

export default function SearchPage(){
  const [term,setTerm]=useState(''); const workspace='org-solarvista';
  const query=useQuery({queryKey:['search',workspace,term],queryFn:()=>apiFetch<{results:any[]}>('/api/v1/search?q='+encodeURIComponent(term),operationalContext(workspace)),enabled:term.trim().length>1});
  return <main className="ops-page"><header><Link href="/">← Mission control</Link><small>GLOBAL SEARCH · TENANT-SCOPED</small><h1>Find operational records</h1><p>Search results only include records within the selected workspace and permitted scope.</p></header><input className="search-input" autoFocus aria-label="Search field operations" placeholder="Search asset, mission, device, work order, or report" value={term} onChange={e=>setTerm(e.target.value)}/>{query.isFetching&&<div className="loading"><span className="spinner"/> Searching…</div>}{query.data?.results?.length===0&&term.length>1&&<div className="empty-state"><h2>No matching operational records</h2><p>Try an asset name, device ID, or mission reference.</p></div>}<section className="search-results">{query.data?.results?.map((result)=><Link href={result.href} key={`${result.type}-${result.id}`}><span>{result.type}</span><b>{result.name}</b><small>{result.status} · {result.id}</small></Link>)}</section></main>
}
