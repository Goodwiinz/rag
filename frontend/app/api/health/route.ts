/**
 * Next.js API Route for Health Check
 *
 * This route proxies health checks to the backend FastAPI service
 * to provide a unified API endpoint for the Next.js frontend.
 */

export async function GET() {
  try {
    // Check backend health
    const backendResponse = await fetch('http://localhost:8000/health', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      // Add cache: no-store to ensure fresh checks
      cache: 'no-store'
    });

    if (!backendResponse.ok) {
      throw new Error(`Backend health check failed: ${backendResponse.status}`);
    }

    const backendHealth = await backendResponse.json();

    // Return combined health status
    return Response.json({
      status: 'healthy',
      frontend: {
        framework: 'Next.js',
        version: '14.2.33',
        status: 'healthy'
      },
      backend: backendHealth,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Health check failed:', error);

    return Response.json({
      status: 'unhealthy',
      frontend: {
        framework: 'Next.js',
        version: '14.2.33',
        status: 'healthy'
      },
      backend: {
        status: 'unhealthy',
        error: error instanceof Error ? error.message : 'Unknown error'
      },
      timestamp: new Date().toISOString()
    }, { status: 503 });
  }
}