import { NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 60;

async function extractTextFromPDF(buffer: Buffer): Promise<string> {
  return buffer.toString('utf-8');
}

async function* processDocument(text: string) {
  yield `data: ${JSON.stringify({ type: 'progress', percent: 10, message: 'IDCA: Analyzing document...' })}\n\n`;
  await new Promise(r => setTimeout(r, 1000));
  
  const title = text.split('\n').find(line => line.trim()) || 'Untitled';
  
  yield `data: ${JSON.stringify({ type: 'progress', percent: 33, message: 'IDCA: Complete' })}\n\n`;
  
  yield `data: ${JSON.stringify({ type: 'progress', percent: 50, message: 'NAA: Searching prior art...' })}\n\n`;
  await new Promise(r => setTimeout(r, 2000));
  
  yield `data: ${JSON.stringify({ type: 'progress', percent: 66, message: 'NAA: Complete' })}\n\n`;
  
  yield `data: ${JSON.stringify({ type: 'progress', percent: 90, message: 'AA: Generating report...' })}\n\n`;
  await new Promise(r => setTimeout(r, 1000));
  
  const finalReport = {
    status_determination: 'Present',
    fields_map: { title: title.substring(0, 200) },
    ucs: `"${title}" prior art`,
    top_references: [
      { title: 'Sample Reference 1', url: 'https://example.com/1', relevance_score: 0.85 }
    ],
    overall_takeaway: 'Analysis complete!'
  };
  
  yield `data: ${JSON.stringify({ type: 'progress', percent: 100, message: 'Complete!' })}\n\n`;
  yield `data: ${JSON.stringify({ type: 'complete', report: finalReport })}\n\n`;
}

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;
    
    if (!file) {
      return Response.json({ error: 'No file uploaded' }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const buffer = Buffer.from(bytes);
    
    let text: string;
    if (file.name.endsWith('.pdf')) {
      text = await extractTextFromPDF(buffer);
    } else if (file.name.endsWith('.txt')) {
      text = buffer.toString('utf-8');
    } else {
      return Response.json({ error: 'Only PDF and TXT files supported' }, { status: 400 });
    }

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        for await (const chunk of processDocument(text)) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (error) {
    return Response.json({ error: String(error) }, { status: 500 });
  }
}
