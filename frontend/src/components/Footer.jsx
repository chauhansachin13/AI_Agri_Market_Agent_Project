export default function Footer() {
  return (
    <footer className="mt-16 border-t border-white/30 py-8 text-center text-xs opacity-70 dark:border-white/10">
      <p>
        Price data from the Government of India{' '}
        <a
          href="https://agmarknet.gov.in/"
          target="_blank"
          rel="noreferrer noopener"
          className="underline underline-offset-2"
        >
          Agmarknet
        </a>{' '}
        and{' '}
        <a
          href="https://www.enam.gov.in/"
          target="_blank"
          rel="noreferrer noopener"
          className="underline underline-offset-2"
        >
          eNAM
        </a>{' '}
        platforms.
      </p>
      <p lang="hi" className="mt-1">
        भाव सरकारी स्रोतों से लिए गए हैं। सौदा करने से पहले मंडी में भाव पक्का कर लें।
      </p>
      <p className="mt-3 opacity-60">
        Recommendations are decision support, not financial advice.
      </p>
    </footer>
  );
}
