import React, { useEffect, useState } from 'react';
import { getLocale, languageKey, translate } from './core';
import { LanguageContext } from './hooks';
export function LanguageProvider({ children }) {
  const [locale, setLocale] = useState(getLocale);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = locale === 'en' ? 'Alddle' : '알뜰알뜰';
  }, [locale]);
  const changeLocale = (next) => {
    const value = next === 'en' ? 'en' : 'ko';
    localStorage.setItem(languageKey, value);
    setLocale(value);
  };
  return <LanguageContext.Provider value={{ locale, setLocale: changeLocale, t: (key, values) => translate(key, values, locale) }}>{children}</LanguageContext.Provider>;
}
