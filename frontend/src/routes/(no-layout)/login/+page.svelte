<script>
  import '../../../app.css';
  import { enhance } from '$app/forms';

  import imgLogo from '$lib/assets/images/logo.png';
  import { ArrowRight } from '@lucide/svelte';

  let isLoading = $state(false);
  let email = $state('');
  let password = $state('');
  let loginError = $state('');

  function handlePasswordLogin() {
    isLoading = true;
    loginError = '';
    return async ({ result }) => {
      isLoading = false;
      if (result?.type === 'failure') {
        loginError = result.data?.error || 'Invalid email or password.';
      } else if (result?.type === 'error' || !result) {
        loginError = 'Something went wrong. Please try again.';
      }
    };
  }
</script>

<svelte:head>
  <title>Sign in | BottleCRM</title>
  <meta
    name="description"
    content="Sign in or sign up for BottleCRM to manage your contacts, deals, and grow your business."
  />
</svelte:head>

<div class="login-page">
  <!-- Main Container -->
  <div class="login-wrapper">
    <!-- Logo -->
    <a href="/" class="logo">
      <img src={imgLogo} alt="" class="logo-icon" />
      <span class="logo-text">BottleCRM</span>
    </a>

    <!-- Login Card -->
    <div class="login-card">
      <h1 class="login-title">Sign in to your account</h1>

      <form method="POST" use:enhance={handlePasswordLogin} class="login-form">
        <input
          type="email"
          name="email"
          placeholder="Email address"
          autocomplete="email"
          class="login-input"
          required
          bind:value={email}
          disabled={isLoading}
        />
        <input
          type="password"
          name="password"
          placeholder="Password"
          autocomplete="current-password"
          class="login-input"
          required
          bind:value={password}
          disabled={isLoading}
        />
        <button type="submit" class="login-btn" disabled={isLoading}>
          {#if isLoading}
            <span class="spinner"></span>
            <span>Signing in...</span>
          {:else}
            <span>Sign in</span>
            <ArrowRight size={16} />
          {/if}
        </button>
      </form>
      {#if loginError}
        <p class="login-error">{loginError}</p>
      {/if}
    </div>

    <!-- Help Links -->
    <div class="help-section">
      <p class="help-text">Use the email and password for your BottleCRM account.</p>
    </div>

    <!-- Footer -->
    <footer class="login-footer">
      <a href="https://bottlecrm.io/privacy-policy">Privacy Policy</a>
      <span class="dot"></span>
      <a href="https://bottlecrm.io/terms">Terms of Service</a>
      <span class="dot"></span>
      <a href="https://github.com/MicroPyramid/Django-CRM" target="_blank" rel="noopener">GitHub</a>
    </footer>
  </div>
</div>

<style>
  .login-page {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f5f8fa;
    padding: 2rem;
  }

  .login-wrapper {
    width: 100%;
    max-width: 400px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  /* Logo */
  .logo {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    text-decoration: none;
    margin-bottom: 2rem;
  }

  .logo-icon {
    width: 40px;
    height: 40px;
    object-fit: contain;
  }

  .logo-text {
    font-size: 1.5rem;
    font-weight: 700;
    color: #33475b;
    letter-spacing: -0.02em;
  }

  /* Login Card */
  .login-card {
    width: 100%;
    background: #fff;
    border-radius: 8px;
    padding: 2.5rem 2rem;
    box-shadow:
      0 1px 3px rgba(0, 0, 0, 0.08),
      0 4px 12px rgba(0, 0, 0, 0.05);
  }

  .login-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: #33475b;
    text-align: center;
    margin: 0 0 1.5rem;
    letter-spacing: -0.01em;
  }

  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .login-form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .login-input {
    width: 100%;
    height: 48px;
    padding: 0 1rem;
    border: 1px solid #cbd6e2;
    border-radius: 6px;
    font-size: 1rem;
    color: #33475b;
    background: #fff;
    outline: none;
    transition: border-color 0.15s ease;
    box-sizing: border-box;
  }

  .login-input:focus {
    border-color: #ff7a59;
  }

  .login-input:disabled {
    opacity: 0.6;
  }

  .login-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    width: 100%;
    height: 48px;
    background: #33475b;
    border: none;
    border-radius: 6px;
    color: #fff;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.15s ease;
  }

  .login-btn:hover {
    background: #2d3e50;
  }

  .login-btn:disabled {
    opacity: 0.85;
    pointer-events: none;
  }

  .login-error {
    margin-top: 0.75rem;
    font-size: 0.875rem;
    color: #c0392b;
    text-align: center;
  }

  /* Help Section */
  .help-section {
    margin-top: 1.5rem;
    text-align: center;
  }

  .help-text {
    font-size: 0.9375rem;
    color: #516f90;
    margin: 0;
  }

  /* Footer */
  .login-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    margin-top: 2rem;
    flex-wrap: wrap;
  }

  .login-footer a {
    font-size: 0.8125rem;
    color: #7c98b6;
    text-decoration: none;
    transition: color 0.15s ease;
  }

  .login-footer a:hover {
    color: #33475b;
  }

  .dot {
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: #cbd6e2;
  }

  /* Responsive */
  @media (max-width: 480px) {
    .login-page {
      padding: 1.5rem;
      align-items: flex-start;
      padding-top: 3rem;
    }

    .login-card {
      padding: 2rem 1.5rem;
    }

    .login-title {
      font-size: 1.375rem;
    }
  }

  /* Dark mode support */
  :global(.dark) .login-page {
    background: #1a1a1a;
  }

  :global(.dark) .login-card {
    background: #2d2d2d;
    box-shadow:
      0 1px 3px rgba(0, 0, 0, 0.2),
      0 4px 12px rgba(0, 0, 0, 0.15);
  }

  :global(.dark) .logo-text {
    color: #fff;
  }

  :global(.dark) .login-title {
    color: #fff;
  }

  :global(.dark) .login-input {
    background: #1a1a1a;
    border-color: #404040;
    color: #fff;
  }

  :global(.dark) .login-input:focus {
    border-color: #ff7a59;
  }

  :global(.dark) .login-btn {
    background: #fff;
    color: #1a1a1a;
  }

  :global(.dark) .login-btn:hover {
    background: #e0e0e0;
  }

  :global(.dark) .help-text {
    color: #999;
  }

  :global(.dark) .login-footer a {
    color: #888;
  }

  :global(.dark) .login-footer a:hover {
    color: #fff;
  }

  :global(.dark) .dot {
    background: #404040;
  }
</style>
