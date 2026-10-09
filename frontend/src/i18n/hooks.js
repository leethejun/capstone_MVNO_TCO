import { createContext, useContext } from 'react';
export const LanguageContext = createContext(null);
export function useI18n() { return useContext(LanguageContext); }
