import zhCN from './locales/zh-CN'
import en from './locales/en'
import ja from './locales/ja'

export const DEFAULT_LOCALE = 'zh-CN'
export const DEFAULT_SINGLE_CAPTURE_SHORTCUT = 'Ctrl+Shift+S'

export const LOCALE_OPTIONS = [
  { value: 'zh-CN', label: '中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
]

export const TRANSLATIONS = {
  'zh-CN': zhCN,
  en,
  ja,
}
