export async function GET() {
  return Response.json({
    status: 'healthy',
    service: 'AMIE Backend',
    perplexity_configured: !!process.env.PERPLEXITY_API_KEY
  });
}
