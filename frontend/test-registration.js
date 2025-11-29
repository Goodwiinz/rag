// Simple test script to validate registration API format
const testRegistration = async () => {
  const testData = {
    email: 'test@example.com',
    password: 'password123',
    first_name: 'Test',
    last_name: 'User',
    organization_name: 'Test Organization'
  };

  console.log('🧪 Testing Registration API Format:');
  console.log('Request payload:', JSON.stringify(testData, null, 2));

  try {
    // This would normally go to your backend API
    const response = await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(testData)
    });

    if (response.ok) {
      console.log('✅ Registration API call successful');
      return { success: true };
    } else {
      const error = await response.json();
      console.log('❌ Registration API call failed:', error);
      return { success: false, error };
    }
  } catch (error) {
    console.log('❌ Network error:', error.message);
    return { success: false, error: error.message };
  }
};

export default testRegistration;