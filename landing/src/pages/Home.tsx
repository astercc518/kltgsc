/**
 * Home — the landing page.
 *
 * Single-page-scroll composition of the 13 sections listed in the
 * rewrite plan. Order is deliberate (visitor mental model from top
 * to bottom): is-this-me → which-product → details → proof → price →
 * objection-defuse → close.
 *
 * Header + Footer wrap the visible scroll area. Section IDs match the
 * Header's in-page nav (#self-serve / #ai-assistant / #pricing).
 */
import Header from '@/sections/Header';
import HeroDual from '@/sections/HeroDual';
import TrustBar from '@/sections/TrustBar';
import ScrollProgress from '@/components/ScrollProgress';
import ProductSelfServe from '@/sections/ProductSelfServe';
import ProductAIAssistant from '@/sections/ProductAIAssistant';
import HowItWorks from '@/sections/HowItWorks';
import Pricing from '@/sections/Pricing';
import PricingCalculator from '@/sections/PricingCalculator';
import UseCases from '@/sections/UseCases';
import Security from '@/sections/Security';
import FAQ from '@/sections/FAQ';
import FinalCTA from '@/sections/FinalCTA';
import Footer from '@/sections/Footer';

export default function Home() {
  return (
    <>
      <ScrollProgress />
      <Header />
      <main>
        <HeroDual />
        <TrustBar />
        <ProductSelfServe />
        <ProductAIAssistant />
        <HowItWorks />
        <Pricing />
        <PricingCalculator />
        <UseCases />
        <Security />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
