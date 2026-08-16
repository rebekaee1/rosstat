/**
 * English body for /privacy and /terms — mirror of the Russian legal pages.
 * Tone: privacy notice for an analytics platform; no obligations beyond the RU original.
 */
import { Link } from 'react-router-dom';
import { Settings2 } from 'lucide-react';
import { track, events } from '../lib/track';
import { openConsentSettings } from '../lib/consent';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';

const h2 = 'text-xl font-semibold text-text-primary mt-10 mb-3';
const p = 'text-text-secondary leading-relaxed mb-4';
const li = 'text-text-secondary leading-relaxed';

function CookieRow({ name, purpose, consent }) {
  return (
    <div className="rounded-xl border border-border-subtle px-4 py-3 mb-2">
      <p className="text-sm font-semibold text-text-primary">{name}</p>
      <p className="text-sm text-text-secondary leading-relaxed mt-0.5">{purpose}</p>
      <p className="text-xs text-text-tertiary mt-1">{consent}</p>
    </div>
  );
}

/** @param {{ t: (key: string) => string, h1: string }} props */
export function PrivacyBodyEn({ t, h1 }) {
  return (
    <>
      <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
        {t('legal.eyebrow')}
      </p>
      <h1 className="font-display text-3xl md:text-4xl font-bold text-text-primary mb-6 leading-tight">
        {h1}
      </h1>
      <p className="text-sm text-text-tertiary mb-8">{t('legal.revised')}</p>

      <h2 className={h2}>1. General provisions</h2>
      <p className={p}>
        This policy sets out how personal data of visitors to{' '}
        <strong className="text-text-primary">forecasteconomy.com</strong> (the Site)
        are processed and what measures are taken to protect them, in accordance with
        Federal Law No. 152-FZ of 27 July 2006 “On Personal Data”.
      </p>
      <p className={p}>
        The personal data controller is IIMPACT PLUS Limited Liability Company
        (IIMPACT PLUS LLC), tax ID (INN) 9705243471, primary state registration number
        (OGRN) 1257700255196, address: 123557, Moscow, Presnensky Val St., 21, premises 172
        (the Controller). The Controller is listed in the Roskomnadzor register of personal
        data controllers under registration number 77-26-538159.
      </p>
      <p className={p}>
        By using the Site, you agree to this policy. Rules for using Site materials are set
        out in the{' '}
        <Link to="/terms" className="text-champagne hover:underline">
          {t('legal.termsLink')}
        </Link>
        .
      </p>

      <h2 className={h2}>2. Data we process</h2>
      <p className={p}>
        Viewing analytics content on the Site is available without an account and without
        providing personal details. Downloading materials and account features are available
        after free registration. The following data are processed:
      </p>
      <ul className="list-disc pl-5 space-y-2 mb-4">
        <li className={li}>
          <strong className="text-text-primary">Technical visitor data</strong> — cookies,
          IP address, browser and device information, pages viewed, and referral source.
          The Site’s own analytics also uses an anonymised random visitor identifier
          (stored in your browser) and derives only country, region, and city from the IP
          address — the IP itself is not stored in the analytics warehouse. Analytics and
          advertising data are processed on the basis of your consent expressed by
          continuing to use the Site after being informed (section 4).
        </li>
        <li className={li}>
          <strong className="text-text-primary">Account data</strong> — when you create an
          account: email address, a protected (irreversibly hashed) password or a sign-in
          identifier from a third-party service (Yandex ID, VK ID), display name; when
          signing in via a third-party service — also phone number (if you provided it to
          the service and allowed it to be transferred), and an internal log of sign-ins
          (date, IP address, browser) for security. Processed on the basis of your explicit
          consent given at registration.
        </li>
        <li className={li}>
          <strong className="text-text-primary">Newsletter consent</strong> — if you tick
          the relevant option at registration, the Controller may send you messages about
          data updates and analytical materials by email and, where available, by phone.
          Consent is voluntary, does not affect access to the Site, and may be withdrawn at
          any time. The fact and date of consent are recorded.
        </li>
        <li className={li}>
          <strong className="text-text-primary">Enquiry data</strong> — email address, name
          (if provided), and the content of messages you send to the Controller by email.
        </li>
      </ul>
      <p className={p}>
        Special categories of personal data and biometric data are not processed.
      </p>

      <h2 className={h2}>3. Purposes and legal bases of processing</h2>
      <ul className="list-disc pl-5 space-y-2 mb-4">
        <li className={li}>
          operating the Site and storing user preferences — as necessary to provide Site
          features;
        </li>
        <li className={li}>
          analysing traffic and improving the Site (web analytics) — on the basis of your
          consent expressed by continuing to use the Site after the cookie banner;
        </li>
        <li className={li}>
          displaying ads from an advertising network — on the basis of your consent
          expressed by continuing to use the Site after the cookie banner;
        </li>
        <li className={li}>
          creating and maintaining an account, authentication, and account security —
          on the basis of your explicit consent given at registration;
        </li>
        <li className={li}>
          responding to enquiries and related correspondence — on the basis of your
          enquiry.
        </li>
      </ul>

      <h2 className={h2}>4. Cookies and consent</h2>
      <p className={p}>
        On the first visit, the Site informs you about cookies via a banner. By continuing
        to use the Site, you consent to cookies in all categories listed below (implied
        consent). Three categories are used:
      </p>
      <CookieRow
        name="Necessary"
        purpose="Store interface preferences and your cookie choices. Required for the Site to work; not transferred to third parties."
        consent="Consent is not required (Art. 6(2) of Law 152-FZ — necessary to provide the service)."
      />
      <CookieRow
        name="Analytics"
        purpose="Yandex Metrica counter: visit statistics, traffic sources, and on-page behaviour. Used to improve the Site."
        consent="Enabled on the basis of consent expressed by continuing to use the Site. You can disable them in cookie settings."
      />
      <CookieRow
        name="Advertising"
        purpose="Yandex Advertising Network: display of ad placements and measurement of impressions."
        consent="Enabled on the basis of consent expressed by continuing to use the Site. You can disable them in cookie settings."
      />
      <p className={p}>
        You may change or withdraw consent for analytics and advertising cookies at any
        time — use the button below or the “Cookie settings” link in the footer of any
        page. Withdrawal stops new cookies of that category; cookies already set can be
        removed in your browser settings.
      </p>
      <button
        type="button"
        onClick={openConsentSettings}
        className={cn(
          FOCUS_RING,
          'inline-flex items-center gap-2 rounded-xl bg-champagne/10 text-champagne px-5 py-2.5 text-sm font-medium hover:bg-champagne/20 transition-colors mb-4',
        )}
      >
        <Settings2 className="w-4 h-4" aria-hidden="true" />
        {t('legal.cookieSettings')}
      </button>

      <h2 className={h2}>5. Transfer to third parties</h2>
      <p className={p}>
        The Controller does not sell or transfer personal data to third parties except as
        described below:
      </p>
      <ul className="list-disc pl-5 space-y-2 mb-4">
        <li className={li}>
          <strong className="text-text-primary">Yandex</strong> (Yandex LLC, Russia) —
          processing of anonymised visit statistics via Yandex Metrica and display of ads
          by the Yandex Advertising Network on the basis of your consent expressed by using
          the Site. The terms of Yandex’s data processing are set out in Yandex’s own
          documents.
        </li>
        <li className={li}>
          when required by authorised public authorities — in cases established by the laws
          of the Russian Federation.
        </li>
      </ul>

      <h2 className={h2}>6. Storage, security, and retention</h2>
      <p className={p}>
        Data are processed by automated means and stored on servers located in the Russian
        Federation. Connection to the Site is protected by HTTPS; access to data is
        restricted. Retention: cookies — for their lifetime or until consent is withdrawn;
        enquiry data — for as long as needed to reply and correspond; visit statistics —
        in anonymised form for the lifetime of the Site. Account data are kept while the
        account exists; when the account is deleted, they and the related sign-in log are
        permanently erased with no possibility of recovery.
      </p>

      <h2 className={h2}>7. Your rights</h2>
      <p className={p}>
        Under Articles 14 and 20 of Law No. 152-FZ you may request information about
        processing of your personal data, ask for correction, blocking, or erasure, and
        withdraw consent. Send a request to an email address in section 9 — a response will
        be given within 10 business days. If you have an account, you may unsubscribe from
        the newsletter and delete your account at any time in account settings; a copy of
        the data processed about you will be provided by the Controller upon request to the
        email addresses above. You may also complain about the Controller’s actions to
        Roskomnadzor or in court.
      </p>

      <h2 className={h2}>8. Policy changes</h2>
      <p className={p}>
        The Controller may update this policy. The new version is published on this page
        with a revised date. For material changes, the Site will ask again for cookie
        consent.
      </p>

      <h2 className={h2}>9. Contact</h2>
      <p className="text-text-secondary leading-relaxed mb-2">
        Questions about this policy and personal-data requests:
      </p>
      <ul className="list-disc pl-5 space-y-1 mb-4">
        <li className={li}>
          <a
            href="mailto:rebeka.ee@yandex.ru"
            className="text-champagne hover:underline"
            onClick={() => track(events.CONTACT_EMAIL)}
          >
            rebeka.ee@yandex.ru
          </a>
        </li>
        <li className={li}>
          <a
            href="mailto:rebeka.ee@aimpact.ru"
            className="text-champagne hover:underline"
            onClick={() => track(events.CONTACT_EMAIL)}
          >
            rebeka.ee@aimpact.ru
          </a>
        </li>
      </ul>
      <p className="text-text-secondary leading-relaxed">
        Postal address of the Controller: 123557, Moscow, Presnensky Val St., 21,
        premises 172, IIMPACT PLUS LLC.
      </p>
    </>
  );
}

/** @param {{ t: (key: string) => string, h1: string }} props */
export function TermsBodyEn({ t, h1 }) {
  return (
    <>
      <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
        {t('legal.eyebrow')}
      </p>
      <h1 className="font-display text-3xl md:text-4xl font-bold text-text-primary mb-6 leading-tight">
        {h1}
      </h1>
      <p className="text-sm text-text-tertiary mb-8">{t('legal.revised')}</p>

      <h2 className={h2}>1. General provisions</h2>
      <p className={p}>
        These terms govern the use of{' '}
        <strong className="text-text-primary">forecasteconomy.com</strong> (the Site).
        The Site is administered by IIMPACT PLUS Limited Liability Company (IIMPACT PLUS LLC),
        tax ID (INN) 9705243471, primary state registration number (OGRN) 1257700255196,
        address: 123557, Moscow, Presnensky Val St., 21, premises 172 (the Administration);
        it is also the personal data controller for visitors. By using the Site, you accept
        these terms. If you do not agree, please stop using the Site.
      </p>

      <h2 className={h2}>2. Purpose of the Site</h2>
      <p className={p}>
        The Site is a free information and analytics platform: macroeconomic indicators for
        Russia and its regions based on official open data (Rosstat, the Bank of Russia,
        the Ministry of Finance of Russia), plus available statistics for selected countries
        from official national and international primary sources; charts, tables, derived
        series, and model-based forecasts. Viewing analytics content does not require an
        account; downloading materials and account features are available after free
        registration.
      </p>
      <p className={p}>
        Creating an account is voluntary and is not required to view analytics. When you
        create an account, you undertake to provide an accurate email address and keep your
        password confidential; you are responsible for actions taken under your account.
        You may delete the account and related data at any time in account settings.
      </p>
      <p className={p}>
        When you register, sign in via a third-party service (Yandex ID, VK ID), or submit
        feedback, the Administration receives and processes the data you provide —
        including email and, if the service shared it with your permission, phone number.
        These data are used to operate the account, respond to your enquiries and, with
        your newsletter consent, to inform you about data updates and analytical materials
        through available channels (email or phone). Newsletter consent is voluntary and may
        be withdrawn at any time. Categories of data, retention, and processing rules are
        described in the{' '}
        <Link to="/privacy" className="text-champagne hover:underline">
          {t('legal.privacyLink')}
        </Link>
        .
      </p>

      <h2 className={h2}>3. Nature of information and disclaimer</h2>
      <ul className="list-disc pl-5 space-y-2 mb-4">
        <li className={li}>
          Site materials are informational and are not personalised investment advice or
          financial, legal, or tax advice.
        </li>
        <li className={li}>
          Forecasts result from statistical modelling, reflect calculated estimates, and do
          not guarantee actual values for future periods.
        </li>
        <li className={li}>
          The Administration aims for accuracy and currency of the data but does not
          guarantee the absence of errors in primary-source data, of delays in their
          publication, or of interruptions in the Site’s operation, and is not liable for
          decisions made on the basis of Site materials.
        </li>
      </ul>

      <h2 className={h2}>4. Use of materials</h2>
      <p className={p}>
        Site materials (text, charts, derived series) may be used freely for personal,
        academic, educational, and editorial purposes provided the source is credited —
        “Forecast Economy” with a link to forecasteconomy.com. Embeddable Site widgets are
        free for any use if the source link inside the widget is preserved. Primary-source
        data belong to the respective agencies and are published by them as open data.
      </p>
      <p className={p}>
        It is prohibited to use the Site in ways that violate the laws of the Russian
        Federation, including actions intended to disrupt the Site, or to create products
        based on Site materials that mislead users about the source of the data.
      </p>

      <h2 className={h2}>5. Advertising</h2>
      <p className={p}>
        The Site may display ad placements from the Yandex Advertising Network. Advertising
        materials are labelled in accordance with advertising law. The Administration is
        not a party to relationships between the user and advertisers.
      </p>

      <h2 className={h2}>6. Personal data and cookies</h2>
      <p className={p}>
        The Site uses cookies, including analytics (Yandex Metrica) and advertising
        (Yandex Advertising Network). By continuing to use the Site after the cookie
        banner, you consent to cookies and related processing. You may withdraw consent and
        configure cookie categories at any time via “Cookie settings” in the Site footer.
        How personal data are processed, which data are collected, retention periods, and
        your rights are described in the{' '}
        <Link to="/privacy" className="text-champagne hover:underline">
          {t('legal.privacyLink')}
        </Link>
        .
      </p>

      <h2 className={h2}>7. Changes to these terms</h2>
      <p className={p}>
        The Administration may amend these terms. The new version is published on this page
        with a revised date and applies from publication. Continued use of the Site after
        publication means acceptance of the new version.
      </p>

      <h2 className={h2}>8. Governing law and contact</h2>
      <p className={p}>
        These terms are governed by the law of the Russian Federation. Questions about the
        Site may be sent to{' '}
        <a
          href="mailto:rebeka.ee@yandex.ru"
          className="text-champagne hover:underline"
          onClick={() => track(events.CONTACT_EMAIL)}
        >
          rebeka.ee@yandex.ru
        </a>{' '}
        or{' '}
        <a
          href="mailto:rebeka.ee@aimpact.ru"
          className="text-champagne hover:underline"
          onClick={() => track(events.CONTACT_EMAIL)}
        >
          rebeka.ee@aimpact.ru
        </a>
        .
      </p>
    </>
  );
}
