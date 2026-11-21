import { useRef } from 'react'
import { BotanicalLogo, HeroIllustration } from './BotanicalEmblem.jsx'

export function LandingPage({
  mode,
  setMode,
  email,
  setEmail,
  password,
  setPassword,
  name,
  setName,
  loading,
  error,
  notice,
  onSubmit,
}) {
  const authSectionRef = useRef(null)
  const registering = mode === 'register'

  const scrollToAuth = () => {
    authSectionRef.current?.scrollIntoView({ behavior: 'smooth' })
    const input = authSectionRef.current?.querySelector('input')
    input?.focus()
  }

  const scrollToFeatures = () => {
    document.getElementById('capabilities')?.scrollIntoView({ behavior: 'smooth' })
  }

  const scrollToHowItWorks = () => {
    document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="landing-page">
      {/* Top Navbar */}
      <nav className="landing-nav" aria-label="Main Navigation">
        <div className="landing-nav-inner">
          <div className="landing-brand">
            <BotanicalLogo size={42} />
            <div className="landing-brand-text">
              <span className="brand-title">Lexora</span>
              <span className="brand-subtitle">Legal Research Assistant</span>
            </div>
          </div>
          <div className="landing-nav-links">
            <button type="button" className="nav-link" onClick={scrollToFeatures}>
              Capabilities
            </button>
            <button type="button" className="nav-link" onClick={scrollToHowItWorks}>
              How It Works
            </button>
            <button type="button" className="nav-cta-btn" onClick={scrollToAuth}>
              {registering ? 'Create Account' : 'Sign In'}
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="landing-hero-section">
        <div className="landing-hero-grid">
          <div className="landing-hero-content">
            <div className="hero-badge">
              <span className="hero-badge-dot"></span>
              Grounded in Indian Legal Sources &amp; Biodiversity Law
            </div>
            <h1 className="landing-hero-title">
              Lexora
              <span className="hero-title-sub">
                Intelligent Legal Research for Ayurveda and Traditional Knowledge
              </span>
            </h1>
            <p className="landing-hero-desc">
              Explore intellectual property, biodiversity regulations, and legal frameworks for Ayurveda with an AI-powered research assistant grounded in legal sources.
            </p>
            <div className="landing-hero-actions">
              <button type="button" className="primary-cta-btn" onClick={scrollToAuth}>
                Start Legal Research
              </button>
              <button type="button" className="secondary-cta-btn" onClick={scrollToFeatures}>
                Explore Capabilities
              </button>
            </div>

            {/* Statutory Trust Chips */}
            <div className="hero-statute-tags">
              <span className="statute-chip">Patents Act, 1970</span>
              <span className="statute-chip">Biological Diversity Act, 2002</span>
              <span className="statute-chip">TKDL Principles</span>
              <span className="statute-chip">AYUSH Guidelines</span>
            </div>
          </div>

          {/* Hero Right: Auth Card with Visual Backdrop */}
          <div className="landing-hero-auth-col" ref={authSectionRef}>
            <div className="auth-card-wrapper">
              <div className="auth-card-backdrop"></div>
              <section className="auth-card" aria-labelledby="auth-title">
                <div className="auth-card-header">
                  <p className="eyebrow">RESEARCH WORKSPACE</p>
                  <h2 id="auth-title">{registering ? 'Create your account' : 'Sign in'}</h2>
                  <p className="auth-description">
                    {registering
                      ? 'Create an account to save your legal research conversations.'
                      : 'Sign in to access your saved research and query legal sources.'}
                  </p>
                </div>

                {notice && <p className="auth-notice" role="status">{notice}</p>}
                {error && <p className="form-error auth-error" role="alert">{error}</p>}

                <form className="auth-form" onSubmit={onSubmit}>
                  {registering && (
                    <label>
                      <span>Name</span>
                      <input
                        autoComplete="name"
                        name="name"
                        required
                        placeholder="Priya Sharma"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                      />
                    </label>
                  )}
                  <label>
                    <span>Email</span>
                    <input
                      autoComplete="email"
                      name="email"
                      type="email"
                      required
                      placeholder="name@example.com"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </label>
                  <label>
                    <span>Password</span>
                    <input
                      autoComplete={registering ? 'new-password' : 'current-password'}
                      name="password"
                      type="password"
                      minLength={registering ? 8 : undefined}
                      required
                      placeholder="••••••••"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                  </label>
                  <button type="submit" className="auth-submit-btn" disabled={loading}>
                    {loading
                      ? (registering ? 'Creating account…' : 'Signing in…')
                      : (registering ? 'Create account' : 'Sign in')}
                  </button>
                </form>

                <p className="auth-switch">
                  {registering ? 'Already have an account?' : 'New to Lexora?'}{' '}
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setMode(registering ? 'login' : 'register')}
                  >
                    {registering ? 'Sign in' : 'Create an account'}
                  </button>
                </p>
                {loading && <p className="visually-hidden" role="status">Please wait</p>}
              </section>
            </div>
          </div>
        </div>
      </header>

      {/* Visual Illustration Showcase */}
      <section className="landing-visual-strip" aria-hidden="true">
        <HeroIllustration />
      </section>

      {/* Features Section */}
      <section id="capabilities" className="landing-features-section">
        <div className="section-header">
          <p className="eyebrow">CORE CAPABILITIES</p>
          <h2>Comprehensive Legal Intelligence</h2>
          <p className="section-subtitle">
            Tailored specifically for Indian intellectual property statutes, biological resource compliance, and Ayurvedic enterprise regulations.
          </p>
        </div>

        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#174C3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
              </svg>
            </div>
            <h3>Intellectual Property Research</h3>
            <p>
              Understand patents, trademarks, copyright, and protection of traditional knowledge under Indian law, including Section 3 statutory exclusions.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#174C3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
                <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
              </svg>
            </div>
            <h3>Biodiversity Regulations</h3>
            <p>
              Explore biological resource access, benefit-sharing, State Biodiversity Board (SBB) intimations under Section 7, and NBA approval pathways.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#174C3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h3>Ayurveda Compliance</h3>
            <p>
              Research legal and regulatory considerations relevant to Ayurvedic products, clinical formulations, and manufacturing businesses.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#174C3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                <path d="M8 7h8M8 11h6" />
              </svg>
            </div>
            <h3>Source-Grounded Answers</h3>
            <p>
              Review retrieved statutory provisions, section citations, and official legal authorities directly supporting every generated response.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#174C3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            </div>
            <h3>Indian &amp; International Frameworks</h3>
            <p>
              Explore relevant national statutes (The Patents Act 1970, Biological Diversity Act 2002) and international IP frameworks available in the corpus.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#174C3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                <path d="M8 9h8M8 13h4" />
              </svg>
            </div>
            <h3>Research Assistance</h3>
            <p>
              Ask questions, explore complex legal concepts, and continue contextual conversations with seamless topic and jurisdiction tracking.
            </p>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="landing-steps-section">
        <div className="section-header">
          <p className="eyebrow">WORKFLOW</p>
          <h2>How Lexora Works</h2>
          <p className="section-subtitle">
            A three-step verification architecture designed to eliminate hallucinations and uphold statutory fidelity.
          </p>
        </div>

        <div className="steps-grid">
          <div className="step-card">
            <div className="step-number">01</div>
            <h3>Ask a Question</h3>
            <p>
              Submit an inquiry on patentability, biological resource sourcing, or Ayurvedic manufacturing regulations with specified jurisdiction.
            </p>
          </div>

          <div className="step-card">
            <div className="step-number">02</div>
            <h3>Retrieve Legal Sources</h3>
            <p>
              Hybrid dense and sparse retrieval scans canonical statutes to extract applicable legal sections, amended clauses, and statutory provisos.
            </p>
          </div>

          <div className="step-card">
            <div className="step-number">03</div>
            <h3>Review Answer &amp; Citations</h3>
            <p>
              Examine the synthesised answer with citations to the relevant legal provisions.
            </p>
          </div>
        </div>
      </section>

      {/* Domain Knowledge Banner */}
      <section className="landing-banner">
        <div className="banner-content">
          <h3>Grounding Indian Traditional Knowledge in Statutory Law</h3>
          <p>
            Bridging classical Ayurvedic formulations with modern intellectual property protection and sustainable biodiversity compliance.
          </p>
          <button type="button" className="banner-cta-btn" onClick={scrollToAuth}>
            Begin Your Inquiry
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <BotanicalLogo size={32} />
            <div>
              <span className="footer-brand-title">Lexora</span>
              <p className="footer-tagline">Legal Research Assistant for Ayurveda &amp; Traditional Knowledge</p>
            </div>
          </div>
          <p className="footer-disclaimer">
            Research and educational purposes only. This tool does not provide legal advice. Check cited source material before relying on an answer.
          </p>
          <p className="footer-copy">
            &copy; {new Date().getFullYear()} Lexora. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
