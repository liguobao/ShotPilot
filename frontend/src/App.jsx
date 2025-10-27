import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Card, Checkbox, Image, Input, InputNumber, Select, Space, Typography } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { DEFAULT_LOCALE, DEFAULT_SINGLE_CAPTURE_SHORTCUT, LOCALE_OPTIONS, TRANSLATIONS } from './i18n'

const { Title, Paragraph, Text } = Typography

const normalizeModifier = (token) => {
  const normalized = token.toLowerCase()
  if (normalized === 'ctrl' || normalized === 'control') return 'ctrl'
  if (normalized === 'shift') return 'shift'
  if (normalized === 'alt' || normalized === 'option') return 'alt'
  if (
    normalized === 'cmd' ||
    normalized === 'command' ||
    normalized === 'meta' ||
    normalized === 'win' ||
    normalized === 'windows' ||
    normalized === 'super'
  ) {
    return 'meta'
  }
  return null
}

const createKeyMatcher = (token) => {
  const cleaned = token.trim()
  if (!cleaned) return null
  const normalized = cleaned.toLowerCase().replace(/\s+/g, '')

  if (/^[a-z0-9]$/.test(normalized)) {
    const value = normalized
    return (event) =>
      typeof event.key === 'string' &&
      event.key.length === 1 &&
      event.key.toLowerCase() === value
  }

  if (/^key[a-z]$/.test(normalized)) {
    const value = normalized.slice(3)
    return (event) =>
      (typeof event.code === 'string' && event.code.toLowerCase() === normalized) ||
      (typeof event.key === 'string' && event.key.length === 1 && event.key.toLowerCase() === value)
  }

  if (/^digit[0-9]$/.test(normalized)) {
    const value = normalized.slice(5)
    return (event) =>
      (typeof event.code === 'string' && event.code.toLowerCase() === normalized) ||
      event.key === value
  }

  if (/^f([1-9]|1[0-9]|2[0-4])$/.test(normalized)) {
    const value = normalized.toUpperCase()
    return (event) => typeof event.key === 'string' && event.key.toUpperCase() === value
  }

  switch (normalized) {
    case 'space':
    case 'spacebar':
      return (event) => event.code === 'Space' || event.key === ' '
    case 'enter':
    case 'return':
      return (event) => event.key === 'Enter'
    case 'escape':
    case 'esc':
      return (event) => event.key === 'Escape'
    case 'tab':
      return (event) => event.key === 'Tab'
    case 'backspace':
      return (event) => event.key === 'Backspace'
    case 'delete':
    case 'del':
      return (event) => event.key === 'Delete'
    case 'home':
      return (event) => event.key === 'Home'
    case 'end':
      return (event) => event.key === 'End'
    case 'pageup':
      return (event) => event.key === 'PageUp'
    case 'pagedown':
      return (event) => event.key === 'PageDown'
    case 'arrowup':
    case 'up':
      return (event) => event.key === 'ArrowUp'
    case 'arrowdown':
    case 'down':
      return (event) => event.key === 'ArrowDown'
    case 'arrowleft':
    case 'left':
      return (event) => event.key === 'ArrowLeft'
    case 'arrowright':
    case 'right':
      return (event) => event.key === 'ArrowRight'
    default:
      return null
  }
}

const parseShortcut = (shortcut, t) => {
  const raw = (shortcut || '').trim()
  if (!raw) {
    return { valid: false, disabled: true, error: null, match: () => false }
  }
  const tokens = raw.split('+').map((token) => token.trim()).filter(Boolean)
  if (!tokens.length) {
    return { valid: false, disabled: false, error: t('messages.hotkeyInvalid'), match: () => false }
  }

  const keyTokenRaw = tokens[tokens.length - 1]
  const modifierTokens = tokens.slice(0, -1)
  const modifiers = { ctrl: false, shift: false, alt: false, meta: false }

  for (const token of modifierTokens) {
    const normalized = normalizeModifier(token)
    if (!normalized) {
      return { valid: false, disabled: false, error: t('messages.hotkeyInvalid'), match: () => false }
    }
    modifiers[normalized] = true
  }

  const keyMatcher = createKeyMatcher(keyTokenRaw)
  if (!keyMatcher) {
    return { valid: false, disabled: false, error: t('messages.hotkeyInvalid'), match: () => false }
  }

  const match = (event) => {
    if (!!modifiers.ctrl !== event.ctrlKey) return false
    if (!!modifiers.shift !== event.shiftKey) return false
    if (!!modifiers.alt !== event.altKey) return false
    if (!!modifiers.meta !== event.metaKey) return false
    return keyMatcher(event)
  }

  return { valid: true, disabled: false, error: null, match }
}

const shouldIgnoreHotkeyEvent = (event) => {
  const target = event.target
  if (!target) return false
  const tagName = typeof target.tagName === 'string' ? target.tagName.toUpperCase() : ''
  if (typeof target.isContentEditable === 'boolean' && target.isContentEditable) return true
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tagName)) return true
  if (typeof target.closest === 'function') {
    const editable = target.closest(
      'input, textarea, select, [contenteditable], [data-hotkey-ignore="true"]'
    )
    if (editable) return true
  }
  return false
}

const getKeyNameFromEvent = (event) => {
  const { code, key } = event
  if (!key) {
    return null
  }
  const normalizedKey = key.toLowerCase()
  if (['control', 'shift', 'alt', 'meta', 'capslock', 'altgraph', 'dead'].includes(normalizedKey)) {
    return null
  }

  if (code) {
    if (code.startsWith('Key') && code.length === 4) {
      return code.slice(3).toUpperCase()
    }
    if (code.startsWith('Digit') && code.length === 6) {
      return code.slice(5)
    }
  }

  const upperKey = key.toUpperCase()
  if (/^F([1-9]|1[0-9]|2[0-4])$/.test(upperKey)) {
    return upperKey
  }

  const specialMap = {
    ' ': 'Space',
    Spacebar: 'Space',
    Space: 'Space',
    Enter: 'Enter',
    Return: 'Enter',
    Escape: 'Esc',
    Esc: 'Esc',
    Tab: 'Tab',
    Backspace: 'Backspace',
    Delete: 'Delete',
    Home: 'Home',
    End: 'End',
    PageUp: 'PageUp',
    PageDown: 'PageDown',
    Insert: 'Insert',
    ArrowUp: 'ArrowUp',
    ArrowDown: 'ArrowDown',
    ArrowLeft: 'ArrowLeft',
    ArrowRight: 'ArrowRight',
  }
  if (specialMap[key]) {
    return specialMap[key]
  }
  if (key.length === 1) {
    return key.toUpperCase()
  }
  return key.charAt(0).toUpperCase() + key.slice(1)
}

const formatShortcutFromEvent = (event) => {
  const modifiers = []
  if (event.ctrlKey || event.key === 'Control') modifiers.push('Ctrl')
  if (event.shiftKey || event.key === 'Shift') modifiers.push('Shift')
  if (event.altKey || event.key === 'Alt' || event.key === 'AltGraph') modifiers.push('Alt')
  if (event.metaKey || event.key === 'Meta') modifiers.push('Command')

  const keyName = getKeyNameFromEvent(event)
  if (!keyName) {
    return null
  }

  const orderedModifiers = []
  const seen = new Set()
  for (const mod of ['Ctrl', 'Shift', 'Alt', 'Command']) {
    if (modifiers.includes(mod) && !seen.has(mod)) {
      orderedModifiers.push(mod)
      seen.add(mod)
    }
  }
  orderedModifiers.push(keyName)
  return orderedModifiers.join('+')
}


function formatTemplate(template, params = {}) {
  if (!template) return ''
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) =>
    Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : ''
  )
}

function usePywebviewApi() {
  const [api, setApi] = useState(() => window.pywebview?.api ?? null)

  useEffect(() => {
    if (api) return

    const assignApi = () => {
      if (window.pywebview?.api) {
        setApi(window.pywebview.api)
      }
    }

    const handleReady = () => assignApi()

    document.addEventListener('pywebviewready', handleReady)

    if (window.pywebview?.ready?.then) {
      window.pywebview.ready.then(assignApi).catch(() => {})
    }

    const pollId = window.setInterval(() => {
      if (window.pywebview?.api) {
        window.clearInterval(pollId)
        assignApi()
      }
    }, 200)

    // Final attempt in case API is already there but event order differed
    assignApi()

    return () => {
      document.removeEventListener('pywebviewready', handleReady)
      window.clearInterval(pollId)
    }
  }, [api])

  return api
}

export default function App() {
  const api = usePywebviewApi()
  const [locale, setLocale] = useState(DEFAULT_LOCALE)
  const [apps, setApps] = useState([])
  const [loadingApps, setLoadingApps] = useState(false)
  const [selectedHwnd, setSelectedHwnd] = useState(null)
  const [intervalSec, setIntervalSec] = useState(0.05)
  const [capturing, setCapturing] = useState(false)
  const [status, setStatus] = useState(null)
  const [message, setMessage] = useState(null)
  const [messageCopyFeedback, setMessageCopyFeedback] = useState(null)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewMeta, setPreviewMeta] = useState(null)
  const [baseDir, setBaseDir] = useState('')
  const [baseDirLoading, setBaseDirLoading] = useState(false)
  const [makeVideo, setMakeVideo] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [previewCollapsed, setPreviewCollapsed] = useState(false)
  const [singleCapturing, setSingleCapturing] = useState(false)
  const [singleCaptureShortcut, setSingleCaptureShortcut] = useState(
    DEFAULT_SINGLE_CAPTURE_SHORTCUT
  )
  const lastCountRef = useRef(0)
  const copyFeedbackTimeoutRef = useRef(null)

  const t = useCallback(
    (key, params) => {
      const current = TRANSLATIONS[locale] || TRANSLATIONS[DEFAULT_LOCALE]
      const fallback = TRANSLATIONS[DEFAULT_LOCALE] || {}
      const template = (current && current[key]) ?? fallback[key] ?? key
      return params ? formatTemplate(template, params) : template
    },
    [locale]
  )

  const localeOptions = useMemo(() => LOCALE_OPTIONS, [])

  const parsedHotkey = useMemo(
    () => parseShortcut(singleCaptureShortcut, t),
    [singleCaptureShortcut, t]
  )

  const showMessage = useCallback((type, content) => {
    setMessage({ type, content, at: Date.now() })
    window.setTimeout(() => {
      setMessage((prev) => {
        if (!prev) return prev
        if (prev.type !== type || prev.content !== content) return prev
        return null
      })
    }, 10000)
  }, [])

  useEffect(() => {
    if (copyFeedbackTimeoutRef.current) {
      window.clearTimeout(copyFeedbackTimeoutRef.current)
      copyFeedbackTimeoutRef.current = null
    }
    setMessageCopyFeedback(null)
  }, [message ? message.at : null, copyFeedbackTimeoutRef])

  useEffect(() => {
    return () => {
      if (copyFeedbackTimeoutRef.current) {
        window.clearTimeout(copyFeedbackTimeoutRef.current)
      }
    }
  }, [copyFeedbackTimeoutRef])

  const handleCopyMessage = useCallback(
    async (content) => {
      if (!content) return
      const text = typeof content === 'string' ? content : String(content)
      try {
        if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text)
        } else {
          const textarea = document.createElement('textarea')
          textarea.value = text
          textarea.setAttribute('readonly', '')
          textarea.style.position = 'fixed'
          textarea.style.left = '-9999px'
          document.body.appendChild(textarea)
          textarea.focus()
          textarea.select()
          const successful = document.execCommand('copy')
          document.body.removeChild(textarea)
          if (!successful) {
            throw new Error('copy_failed')
          }
        }
        setMessageCopyFeedback('success')
      } catch {
        setMessageCopyFeedback('error')
      } finally {
        if (copyFeedbackTimeoutRef.current) {
          window.clearTimeout(copyFeedbackTimeoutRef.current)
        }
        copyFeedbackTimeoutRef.current = window.setTimeout(() => {
          setMessageCopyFeedback(null)
          copyFeedbackTimeoutRef.current = null
        }, 2000)
      }
    },
    [copyFeedbackTimeoutRef]
  )

  useEffect(() => {
    if (!api?.get_language) {
      return
    }
    let cancelled = false
    const loadLanguage = async () => {
      try {
        const res = await api.get_language()
        if (!cancelled && res?.success) {
          const lang = res.data?.language
          if (lang && TRANSLATIONS[lang]) {
            setLocale(lang)
          }
        }
      } catch {
        /* silent */
      }
    }
    loadLanguage()
    return () => {
      cancelled = true
    }
  }, [api])

  const handleChangeLocale = useCallback(
    async (value) => {
      if (value === locale) return
      const previous = locale
      setLocale(value)
      if (!api?.set_language) {
        return
      }
      try {
        const res = await api.set_language(value)
        if (!res?.success) {
          throw new Error(res?.message || '')
        }
      } catch (err) {
        setLocale(previous)
        const detail = err instanceof Error && err.message ? `: ${err.message}` : ''
        showMessage('error', `${t('messages.languageChangeError')}${detail}`)
      }
    },
    [api, locale, showMessage, t]
  )

  useEffect(() => {
    document.title = t('app.title')
  }, [t])

  const openPath = useCallback(
    (dir) => {
      if (!dir) return
      window.pywebview?.api
        ?.open_path(dir)
        ?.catch(() => showMessage('error', t('messages.openPathError')))
    },
    [showMessage, t]
  )

  const fetchApps = useCallback(async () => {
    if (!api) {
      showMessage('error', t('messages.refreshAppsMissingApi'))
      return
    }

    const listAppsFn = api.list_apps ?? api.list_app
    if (typeof listAppsFn !== 'function') {
      showMessage('error', t('messages.refreshAppsMissingApi'))
      return
    }

    setLoadingApps(true)
    try {
      const res = await listAppsFn.call(api)
      if (!res?.success) {
        throw new Error(res?.message || t('messages.refreshAppsError'))
      }
      setApps(res.data || [])
      if (res.data?.length) {
        setSelectedHwnd((prev) => prev ?? res.data[0].hwnd)
      }
    } catch (err) {
      showMessage('error', err.message || t('messages.refreshAppsError'))
    } finally {
      setLoadingApps(false)
    }
  }, [api, showMessage, t])

  const minimizeAppWindow = useCallback(async () => {
    if (!api?.minimize_window) return
    try {
      const res = await api.minimize_window()
      if (res && res.success === false) {
        throw new Error(res.message || t('messages.windowMinimizeError'))
      }
    } catch (err) {
      const messageText =
        err instanceof Error
          ? err.message || t('messages.windowMinimizeError')
          : t('messages.windowMinimizeError')
      showMessage('error', messageText)
    }
  }, [api, showMessage, t])

  const restoreAppWindow = useCallback(async () => {
    if (!api?.restore_window) return
    try {
      const res = await api.restore_window()
      if (res && res.success === false) {
        throw new Error(res.message || t('messages.windowRestoreError'))
      }
    } catch (err) {
      const messageText =
        err instanceof Error
          ? err.message || t('messages.windowRestoreError')
          : t('messages.windowRestoreError')
      showMessage('error', messageText)
    }
  }, [api, showMessage, t])

  const handleStart = useCallback(async () => {
    if (!api) {
      showMessage('error', t('messages.apiUnavailableStart'))
      return
    }
    if (!selectedHwnd) {
      showMessage('warning', t('messages.selectWindowRequired'))
      return
    }

    try {
      lastCountRef.current = 0
      const res = await api.start_capture(
        selectedHwnd,
        intervalSec,
        baseDir || undefined,
        makeVideo,
      )
      if (!res?.success) {
        throw new Error(res?.message || t('messages.captureStartError'))
      }
      setCapturing(true)
      setStatus({
        running: true,
        current: res.data || null,
        last_error: null,
        count: res.data?.count ?? 0,
        last_file: res.data?.last_file ?? null,
        make_video: res.data?.make_video ?? makeVideo,
        video_path: res.data?.video_path ?? null,
      })
      lastCountRef.current = res.data?.count ?? 0
      await minimizeAppWindow()
      const directory = res.data?.output_dir || baseDir || t('status.noDirectory')
      showMessage(
        'success',
        t('messages.captureStartSuccess', {
          title: res.data?.title || t('labels.untitledWindow'),
          dir: directory,
        })
      )
    } catch (err) {
      showMessage('error', err.message || t('messages.captureStartError'))
    }
  }, [api, baseDir, intervalSec, makeVideo, minimizeAppWindow, selectedHwnd, showMessage, t])

  const handleStop = useCallback(async () => {
    if (!api) {
      showMessage('error', t('messages.apiUnavailableStop'))
      return
    }

    try {
      const res = await api.stop_capture()
      if (!res?.success) {
        throw new Error(res?.message || t('messages.noRunningTask'))
      }
      const totalCount = res?.data?.count ?? 0
      const videoPath = res?.data?.video_path
      setCapturing(false)
      lastCountRef.current = 0
      setStatus((prev) => {
        const wasMakingVideo = prev?.current?.make_video ?? makeVideo
        const currentInfo = prev?.current
          ? {
              ...prev.current,
              count: 0,
              make_video: wasMakingVideo,
              video_path: videoPath || prev.current.video_path || null,
            }
          : null
        return {
          running: false,
          current: currentInfo,
          last_error: null,
          count: 0,
          last_file: null,
          video_path: videoPath || null,
          make_video: wasMakingVideo,
        }
      })
      const stopMessage = videoPath
        ? t('messages.captureStopSuccessWithVideo', {
            count: totalCount,
            path: videoPath,
          })
        : t('messages.captureStopSuccess', { count: totalCount })
      showMessage(videoPath ? 'success' : 'info', stopMessage)

      const statusRes = await api.get_status()
      if (statusRes?.success) {
        const data = statusRes.data || {}
        setStatus((prev) => {
          const fallbackVideo =
            data?.video_path ?? videoPath ?? prev?.video_path ?? null
          const makeVideoFlag =
            data?.make_video ??
            prev?.make_video ??
            prev?.current?.make_video ??
            makeVideo
          const currentInfo =
            prev?.current ||
            (data?.current
              ? {
                  ...data.current,
                  count: 0,
                  video_path: data.current.video_path ?? fallbackVideo,
                  make_video: data.current.make_video ?? makeVideoFlag,
                }
              : null)
          return {
            running: data?.running ?? false,
            current: currentInfo,
            last_error: data?.last_error ?? null,
            count: 0,
            last_file: null,
            video_path: fallbackVideo,
            make_video: makeVideoFlag,
          }
        })
      }
    } catch (err) {
      showMessage('error', err.message || t('messages.captureStopError'))
    } finally {
      await restoreAppWindow()
    }
  }, [api, makeVideo, restoreAppWindow, showMessage, t])

  const handleSingleCapture = useCallback(async () => {
    if (!api) {
      showMessage('error', t('messages.apiUnavailableSingle'))
      return
    }
    if (!selectedHwnd) {
      showMessage('warning', t('messages.selectWindowRequired'))
      return
    }

    try {
      setSingleCapturing(true)
      const res = await api.capture_once(selectedHwnd)
      if (!res?.success) {
        throw new Error(res?.message || t('messages.singleCaptureError'))
      }
      const path =
        res?.data?.path ?? (typeof res?.data === 'string' ? res.data : null)
      const successMessage = path
        ? t('messages.singleCaptureSuccess', { path })
        : t('messages.singleCaptureFallback')
      showMessage('success', successMessage)
    } catch (err) {
      showMessage('error', err.message || t('messages.singleCaptureError'))
    } finally {
      setSingleCapturing(false)
    }
  }, [api, selectedHwnd, showMessage, t])

  useEffect(() => {
    if (parsedHotkey.disabled || !parsedHotkey.valid) {
      return
    }
    const handler = (event) => {
      if (shouldIgnoreHotkeyEvent(event)) {
        return
      }
      if (parsedHotkey.match(event)) {
        event.preventDefault()
        handleSingleCapture()
      }
    }
    window.addEventListener('keydown', handler)
    return () => {
      window.removeEventListener('keydown', handler)
    }
  }, [handleSingleCapture, parsedHotkey])

  const fetchPreview = useCallback(
    async (hwnd, options = {}) => {
      const { silent = false, skipLoading = false } = options
      if (!api || !hwnd) return
      if (!skipLoading) {
        setPreviewLoading(true)
      }
      try {
        const res = await api.preview_capture(hwnd)
        if (!res?.success) {
          throw new Error(res?.message || t('messages.previewError'))
        }
        if (res.data?.image) {
          setPreview(res.data.image)
          setPreviewMeta(res.data.meta || null)
        } else {
          setPreview(res.data || null)
          setPreviewMeta(null)
        }
      } catch (err) {
        if (!silent) {
          setPreview(null)
          setPreviewMeta(null)
          showMessage('error', err.message || t('messages.previewError'))
        }
      } finally {
        if (!skipLoading) {
          setPreviewLoading(false)
        }
      }
    },
    [api, showMessage, t]
  )

  useEffect(() => {
    if (!api) return
    fetchApps()
  }, [api, fetchApps])

  useEffect(() => {
    if (!api || baseDir) return
    let cancelled = false
    const loadDefaultDir = async () => {
      try {
        const res = await api.get_default_directory()
        if (!cancelled && res?.success && res.data) {
          setBaseDir(res.data)
        }
      } catch {
        /* ignore default dir errors */
      }
    }
    loadDefaultDir()
    return () => {
      cancelled = true
    }
  }, [api, baseDir])

  useEffect(() => {
    if (!api || !capturing) return

    let mounted = true
    const timer = window.setInterval(async () => {
      try {
        const res = await api.get_status()
        if (!mounted) return
        if (res?.success) {
          const statusData = res.data || null
          setStatus(statusData)
          if (!statusData?.running) {
            setCapturing(false)
            restoreAppWindow()
          }
          const statusCount =
            statusData?.current?.count ?? statusData?.count ?? lastCountRef.current
          const currentHwnd = statusData?.current?.hwnd
          if (
            typeof statusCount === 'number' &&
            statusCount !== lastCountRef.current &&
            selectedHwnd &&
            (currentHwnd === undefined ||
              currentHwnd === null ||
              Number(currentHwnd) === Number(selectedHwnd))
          ) {
            lastCountRef.current = statusCount
            fetchPreview(selectedHwnd, { silent: true, skipLoading: true })
          } else if (typeof statusCount === 'number') {
            lastCountRef.current = statusCount
          }
        }
      } catch {
        /* ignore polling errors */
      }
    }, 1000)

    return () => {
      mounted = false
      window.clearInterval(timer)
    }
  }, [api, capturing, fetchPreview, restoreAppWindow, selectedHwnd])

  useEffect(() => {
    if (!selectedHwnd) {
      setPreview(null)
      setPreviewMeta(null)
      return
    }
    fetchPreview(selectedHwnd)
  }, [selectedHwnd, fetchPreview])

  const statusAlert = useMemo(() => {
    const lastError = status?.last_error
    if (!lastError) return null
    return (
      <Alert
        type="error"
        showIcon
        message={t('status.errorTitle')}
        description={lastError}
      />
    )
  }, [status, t])

  const messageAlert = useMemo(() => {
    if (!message) return null
    const isError = message.type === 'error'
    const feedbackText =
      messageCopyFeedback === 'success'
        ? t('messages.copySuccess')
        : messageCopyFeedback === 'error'
          ? t('messages.copyFailed')
          : null
    return (
      <Alert
        type={message.type}
        showIcon
        message={message.content}
        closable
        onClose={() => setMessage(null)}
        action={
          isError ? (
            <Space size="small">
              {feedbackText ? (
                <Text type={messageCopyFeedback === 'success' ? 'success' : 'danger'}>
                  {feedbackText}
                </Text>
              ) : null}
              <Button
                size="small"
                type="link"
                onClick={() => handleCopyMessage(message.content)}
              >
                {t('buttons.copy')}
              </Button>
            </Space>
          ) : null
        }
      />
    )
  }, [handleCopyMessage, message, messageCopyFeedback, t])

  const options = useMemo(() => {
    return apps.map((app) => {
      const isMonitor = app.monitor && typeof app.monitor === 'object'
      const fallbackTitle = isMonitor ? t('labels.monitor') : t('labels.untitledWindow')
      const label = (app.title && app.title.trim()) || fallbackTitle
      const descParts = []
      if (isMonitor) {
        if (app.monitor?.device) {
          descParts.push(app.monitor.device)
        }
        if (
          typeof app.monitor?.width === 'number' &&
          typeof app.monitor?.height === 'number'
        ) {
          descParts.push(`${app.monitor.width} × ${app.monitor.height}`)
        }
        if (app.monitor?.primary) {
          descParts.push(t('labels.monitorPrimary'))
        }
      } else {
        descParts.push(app.process || t('labels.unknownProcess'))
        descParts.push(app.hwnd_hex || app.hwnd)
      }
      const description = descParts.filter(Boolean).join(' · ')
      const keywords = [
        label,
        app.process || '',
        app.hwnd_hex || '',
        description,
        isMonitor ? t('labels.monitor') : '',
      ]
        .filter(Boolean)
        .join(' ')
      return {
        label,
        value: app.hwnd,
        description,
        keywords,
        data: {
          label,
          description,
        },
      }
    })
  }, [apps, t])

  const selectedAppDetail = useMemo(() => {
    if (!selectedHwnd) return null
    return apps.find((app) => app.hwnd === selectedHwnd) || null
  }, [apps, selectedHwnd])

  const detailLines = useMemo(() => {
    if (!selectedAppDetail) return null
    const isMonitor =
      selectedAppDetail.monitor && typeof selectedAppDetail.monitor === 'object'
    const title =
      (selectedAppDetail.title && selectedAppDetail.title.trim()) ||
      (isMonitor ? t('labels.monitor') : t('labels.untitledWindow'))
    const processLabel = isMonitor ? t('labels.type') : t('labels.process')
    const process =
      (isMonitor ? t('labels.monitor') : selectedAppDetail.process) ||
      t('labels.unknownProcess')
    const hwndHex = selectedAppDetail.hwnd_hex || selectedAppDetail.hwnd
    const monitorInfo = isMonitor ? selectedAppDetail.monitor || {} : null
    const hasMonitorSize =
      monitorInfo &&
      typeof monitorInfo.width === 'number' &&
      typeof monitorInfo.height === 'number'
    const fallbackSize = hasMonitorSize
      ? `${monitorInfo.width} × ${monitorInfo.height}`
      : null
    const rect = previewMeta?.rect
    const sizeLine = rect ? `${rect.width} × ${rect.height}` : fallbackSize
    return {
      title,
      processLabel,
      process,
      hwndHex,
      sizeLine,
      isMonitor,
      monitorDevice:
        monitorInfo && monitorInfo.device ? monitorInfo.device : null,
      monitorPrimary: Boolean(monitorInfo && monitorInfo.primary),
    }
  }, [previewMeta, selectedAppDetail, t])

  const captureCount = capturing
    ? status?.current?.count ?? status?.count ?? lastCountRef.current ?? 0
    : 0

  const isCaptureRunning = capturing || Boolean(status?.running)
  const currentOutputDir = isCaptureRunning
    ? status?.current?.output_dir || baseDir || null
    : null

  const handleChooseDirectory = useCallback(async () => {
    if (!api) {
      showMessage('error', t('messages.apiUnavailableDirectory'))
      return
    }
    setBaseDirLoading(true)
    try {
      const res = await api.choose_directory(baseDir || undefined)
      if (!res?.success) {
        if (res?.code === 'directory_not_selected') {
          return
        }
        if (res?.message) {
          showMessage('error', res.message)
        } else {
          showMessage('error', t('messages.chooseDirError'))
        }
        return
      }
      setBaseDir(res.data)
    } catch (err) {
      showMessage('error', err.message || t('messages.chooseDirError'))
    } finally {
      setBaseDirLoading(false)
    }
  }, [api, baseDir, showMessage, t])

  return (
    <div
      style={{
        background: '#f5f5f5',
        padding: 24,
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          width: '100%',
          margin: '0 auto',
        }}
      >
        <Card
          style={{ width: '100%' }}
          bodyStyle={{ padding: 28 }}
        >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: 16,
              flexWrap: 'wrap',
            }}
          >
            <div>
              <Title level={3} style={{ marginBottom: 8 }}>
                {t('app.title')}
              </Title>
              <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                {t('app.subtitle')}
              </Paragraph>
            </div>
            <Space size={6} align="center">
              <Space size={4} align="center">
                <GlobalOutlined style={{ color: 'rgba(0,0,0,0.45)' }} />
                <Text type="secondary">{t('labels.language')}</Text>
              </Space>
              <Select
                size="large"
                value={locale}
                onChange={handleChangeLocale}
                options={localeOptions}
                style={{ width: 120 }}
              />
            </Space>
          </div>

          {messageAlert}

          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div
              style={{
                display: 'flex',
                gap: 12,
                alignItems: 'center',
                flexWrap: 'wrap',
              }}
            >
              <Select
                style={{ flex: '1 1 360px', minWidth: 320 }}
                size="large"
                placeholder={t('placeholders.windowSelect')}
                options={options}
                loading={loadingApps}
                value={selectedHwnd}
                onChange={setSelectedHwnd}
                showSearch
                optionFilterProp="keywords"
                optionLabelProp="label"
                notFoundContent={t('controls.noWindows')}
                dropdownMatchSelectWidth={false}
                dropdownStyle={{ minWidth: 520 }}
                optionRender={(option) => (
                  <Space direction="vertical" size={2}>
                    <Text>{option.data.label}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {option.data.description}
                    </Text>
                  </Space>
                )}
              />
              <Button onClick={fetchApps} loading={loadingApps} size="large">
                {t('buttons.refresh')}
              </Button>
              <Button
                size="large"
                onClick={() => fetchPreview(selectedHwnd)}
                loading={previewLoading}
                disabled={!selectedHwnd}
              >
                {t('buttons.refreshPreview')}
              </Button>
              <div
                style={{
                  marginLeft: 'auto',
                  display: 'flex',
                  gap: 12,
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                <Button
                  type="link"
                  style={{ padding: 0 }}
                  onClick={() => setShowAdvanced((prev) => !prev)}
                >
                  {showAdvanced ? t('buttons.hideAdvanced') : t('buttons.advanced')}
                </Button>
              </div>
            </div>

            {showAdvanced ? (
              <>
                <div
                  style={{
                    display: 'flex',
                    gap: 12,
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    flexGrow: 1,
                  }}
                >
                  <Text style={{ minWidth: 96, whiteSpace: 'nowrap' }}>
                    {t('labels.captureInterval')}
                  </Text>
                  <InputNumber
                    size="large"
                    min={0.01}
                    max={60}
                    step={0.01}
                    precision={2}
                    value={intervalSec}
                    onChange={(value) => {
                      const next =
                        typeof value === 'number' && !Number.isNaN(value) ? value : 0.5
                      setIntervalSec(next)
                    }}
                  />
                  <Checkbox
                    checked={makeVideo}
                    onChange={(e) => setMakeVideo(e.target.checked)}
                    disabled={capturing}
                  >
                    {t('labels.makeVideo')}
                  </Checkbox>
                </div>

                <div
                  style={{
                    display: 'flex',
                    gap: 12,
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    width: '100%',
                  }}
                >
                  <Text style={{ minWidth: 96, whiteSpace: 'nowrap' }}>
                    {t('labels.saveDirectory')}
                  </Text>
                  <Input
                    size="large"
                    readOnly
                    value={baseDir}
                    placeholder={t('placeholders.saveDirectory')}
                    style={{
                      flex: 1,
                      cursor:
                        capturing &&
                        (status?.current?.output_dir || baseDir)
                          ? 'pointer'
                          : 'default',
                      userSelect: 'none',
                    }}
                    onClick={() => {
                      if (!capturing) {
                        return
                      }
                      const dirToOpen =
                        status?.current?.output_dir || baseDir
                      if (!dirToOpen) return
                      openPath(dirToOpen)
                    }}
                  />
                  <Button
                    size="large"
                    onClick={handleChooseDirectory}
                    loading={baseDirLoading}
                  >
                    {t('buttons.browse')}
                  </Button>
                </div>

                <div
                  style={{
                    display: 'flex',
                    gap: 12,
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    width: '100%',
                  }}
                >
                  <Text style={{ minWidth: 96, whiteSpace: 'nowrap' }}>
                    {t('labels.singleCaptureHotkey')}
                  </Text>
                  <Input
                    size="large"
                    value={singleCaptureShortcut}
                    onChange={(event) => setSingleCaptureShortcut(event.target.value ?? '')}
                    onKeyDown={(event) => {
                      if (event.key === 'Tab') {
                        return
                      }
                      event.preventDefault()
                      event.stopPropagation()
                      if (['Backspace', 'Delete', 'Escape'].includes(event.key)) {
                        setSingleCaptureShortcut('')
                        return
                      }
                      if (event.repeat) {
                        return
                      }
                      const formatted = formatShortcutFromEvent(event)
                      if (formatted) {
                        setSingleCaptureShortcut(formatted)
                      }
                    }}
                    onPaste={(event) => {
                      const text = event.clipboardData?.getData('text')
                      if (typeof text === 'string') {
                        event.preventDefault()
                        setSingleCaptureShortcut(text.trim())
                      }
                    }}
                    placeholder={t('placeholders.hotkey')}
                    allowClear
                    status={parsedHotkey.error ? 'error' : undefined}
                    style={{ flex: '0 1 200px' }}
                    data-hotkey-ignore="true"
                    autoComplete="off"
                    spellCheck={false}
                    inputMode="none"
                  />
                </div>
                <div style={{ paddingLeft: 96, width: '100%' }}>
                  {parsedHotkey.error ? (
                    <Text type="danger">{parsedHotkey.error}</Text>
                  ) : parsedHotkey.disabled ? (
                    <Text type="secondary">{t('messages.hotkeyDisabled')}</Text>
                  ) : (
                    <Text type="secondary">
                      {t('messages.hotkeyHelp', { shortcut: DEFAULT_SINGLE_CAPTURE_SHORTCUT })}
                    </Text>
                  )}
                </div>
              </>
            ) : null}
          </Space>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              flexWrap: 'wrap',
            }}
          >
            <Space size="middle" wrap>
              <Button
                size="large"
                onClick={handleSingleCapture}
                loading={singleCapturing}
                disabled={!selectedHwnd || singleCapturing}
              >
                {t('buttons.singleCapture')}
              </Button>
              <Button
                type="primary"
                size="large"
                onClick={handleStart}
                disabled={!selectedHwnd || capturing}
              >
                {t('buttons.start')}
              </Button>
              <Button
                danger
                size="large"
                onClick={handleStop}
                disabled={!capturing}
              >
                {t('buttons.stop')}
              </Button>
              {currentOutputDir ? (
                <Button
                  type="link"
                  style={{
                    padding: 0,
                    maxWidth: 360,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  onClick={() => openPath(currentOutputDir)}
                  title={currentOutputDir}
                >
                  {currentOutputDir}
                </Button>
              ) : null}
            </Space>
            <Text type="secondary" style={{ whiteSpace: 'nowrap' }}>
              {t('text.captureCount', { count: captureCount })}
            </Text>
          </div>

          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {previewCollapsed ? (
              <Button
                type="link"
                style={{ padding: 0, alignSelf: 'flex-start' }}
                onClick={() => setPreviewCollapsed(false)}
              >
                {t('buttons.expandPreview')}
              </Button>
            ) : (
              <Card
                size="small"
                style={{ width: '100%' }}
                bodyStyle={{ padding: 12 }}
                title={
                  detailLines ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <Text strong style={{ fontSize: 14 }}>{detailLines.title}</Text>
                      <Space size={6} wrap style={{ fontSize: 12 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {detailLines.processLabel}：{detailLines.process}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {t('labels.windowHandle')}：{detailLines.hwndHex}
                        </Text>
                        {detailLines.sizeLine ? (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {t('labels.size')}：{detailLines.sizeLine}
                          </Text>
                        ) : null}
                        {detailLines.monitorDevice ? (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {t('labels.device')}：{detailLines.monitorDevice}
                          </Text>
                        ) : null}
                        {detailLines.monitorPrimary ? (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {t('labels.monitorPrimary')}
                          </Text>
                        ) : null}
                      </Space>
                    </div>
                  ) : (
                    t('preview.title')
                  )
                }
                extra={
                  <Space size="small">
                    {previewLoading ? (
                      <Text type="secondary">{t('status.previewLoading')}</Text>
                    ) : null}
                    <Button
                      type="link"
                      style={{ padding: 0 }}
                      onClick={() => setPreviewCollapsed(true)}
                    >
                      {t('buttons.collapsePreview')}
                    </Button>
                  </Space>
                }
              >
                <div style={{ position: 'relative', width: '100%' }}>
                  {preview ? (
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        maxHeight: 320,
                        overflow: 'hidden',
                      }}
                    >
                      <Image
                        src={preview}
                        alt={t('preview.title')}
                        style={{ maxWidth: '100%', maxHeight: 300, objectFit: 'contain' }}
                        preview={{ mask: t('preview.mask') }}
                      />
                    </div>
                  ) : (
                    <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      {t('status.previewPlaceholder')}
                    </Paragraph>
                  )}
                </div>
              </Card>
            )}
          </Space>

          {statusAlert}
        </Space>
        </Card>
      </div>
    </div>
  )
}
