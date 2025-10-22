import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Card, Checkbox, Image, Input, InputNumber, Select, Space, Typography } from 'antd'

const { Title, Paragraph, Text } = Typography

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
  const [apps, setApps] = useState([])
  const [loadingApps, setLoadingApps] = useState(false)
  const [selectedHwnd, setSelectedHwnd] = useState(null)
  const [intervalSec, setIntervalSec] = useState(0.5)
  const [capturing, setCapturing] = useState(false)
  const [status, setStatus] = useState(null)
  const [message, setMessage] = useState(null)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewMeta, setPreviewMeta] = useState(null)
  const [baseDir, setBaseDir] = useState('')
  const [baseDirLoading, setBaseDirLoading] = useState(false)
  const [makeVideo, setMakeVideo] = useState(false)
  const lastCountRef = useRef(0)

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

  const openPath = useCallback(
    (dir) => {
      if (!dir) return
      window.pywebview?.api
        ?.open_path(dir)
        ?.catch(() => showMessage('error', '无法打开目录，请手动查看'))
    },
    [showMessage]
  )

  const fetchApps = useCallback(async () => {
    if (!api) {
      showMessage('error', 'pywebview 接口尚未就绪，请在桌面应用中打开此页面。')
      return
    }

    setLoadingApps(true)
    try {
      const res = await api.list_apps()
      if (!res?.success) {
        throw new Error(res?.message || '无法获取窗口列表')
      }
      setApps(res.data || [])
      if (res.data?.length) {
        // 默认选中第一项
        setSelectedHwnd((prev) => prev ?? res.data[0].hwnd)
      }
    } catch (err) {
      showMessage('error', err.message || '获取窗口列表失败')
    } finally {
      setLoadingApps(false)
    }
  }, [api, makeVideo, showMessage])

  const handleStart = useCallback(async () => {
    if (!api) {
      showMessage('error', 'pywebview 接口不可用，无法启动截屏。')
      return
    }
    if (!selectedHwnd) {
      showMessage('warning', '请选择要截屏的窗口。')
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
        throw new Error(res?.message || '截屏启动失败')
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
      showMessage(
        'success',
        `开始截屏：${res.data?.title || '窗口'}，保存目录 ${res.data?.output_dir}`
      )
    } catch (err) {
      showMessage('error', err.message || '截屏启动失败')
    }
  }, [api, intervalSec, selectedHwnd, baseDir, makeVideo, showMessage])

  const handleStop = useCallback(async () => {
    if (!api) {
      showMessage('error', 'pywebview 接口不可用，无法停止截屏。')
      return
    }

    try {
      const res = await api.stop_capture()
      if (!res?.success) {
        throw new Error(res?.message || '没有运行中的任务')
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
        ? `截屏任务已停止，共 ${totalCount} 张，视频已生成：${videoPath}`
        : `截屏任务已停止，共 ${totalCount} 张。`
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
      showMessage('error', err.message || '停止截屏失败')
    }
  }, [api, showMessage])

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
          throw new Error(res?.message || '预览失败')
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
          showMessage('error', err.message || '无法获取截图预览')
        }
      } finally {
        if (!skipLoading) {
          setPreviewLoading(false)
        }
      }
    },
    [api, showMessage]
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
  }, [api, capturing, fetchPreview, selectedHwnd])

  useEffect(() => {
    if (!selectedHwnd) {
      setPreview(null)
      setPreviewMeta(null)
      return
    }
    fetchPreview(selectedHwnd)
  }, [selectedHwnd, fetchPreview])

  const statusAlert = useMemo(() => {
    if (!status) return null
    if (status.last_error) {
      return (
        <Alert
          type="error"
          showIcon
          message="截屏任务出现异常"
          description={status.last_error}
        />
      )
    }
    if (status.running && status.current) {
      const dir = status.current.output_dir
      return (
        <Alert
          type="info"
          showIcon
          message="正在截屏"
          description={
            dir ? (
              <Button
                type="link"
                style={{ padding: 0 }}
                onClick={() => openPath(dir)}
              >
                {dir}
              </Button>
            ) : (
              <Text type="secondary">未获取保存目录</Text>
            )
          }
        />
      )
    }
    return null
  }, [status, openPath])

  const messageAlert = useMemo(() => {
    if (!message) return null
    return (
      <Alert
        type={message.type}
        showIcon
        message={message.content}
        closable
        onClose={() => setMessage(null)}
      />
    )
  }, [message])

  const options = useMemo(() => {
    return apps.map((app) => ({
      label: app.title || '（无标题窗口）',
      value: app.hwnd,
      description: `${app.process || '未知进程'} · ${app.hwnd_hex || app.hwnd}`,
      keywords: `${app.title || ''} ${app.process || ''} ${app.hwnd_hex || ''}`,
    }))
  }, [apps])

  const selectedAppDetail = useMemo(() => {
    if (!selectedHwnd) return null
    return apps.find((app) => app.hwnd === selectedHwnd) || null
  }, [apps, selectedHwnd])

  const detailLines = useMemo(() => {
    if (!selectedAppDetail) return null
    const title = selectedAppDetail.title || '未知窗口'
    const process = selectedAppDetail.process || '未知进程'
    const hwndHex = selectedAppDetail.hwnd_hex || selectedAppDetail.hwnd
    const rect = previewMeta?.rect
    const sizeLine = rect ? `${rect.width} × ${rect.height}` : null
    return {
      title,
      process,
      hwndHex,
      sizeLine,
    }
  }, [selectedAppDetail, previewMeta])

  const captureCount = capturing
    ? status?.current?.count ?? status?.count ?? lastCountRef.current ?? 0
    : 0

  const handleChooseDirectory = useCallback(async () => {
    if (!api) {
      showMessage('error', 'pywebview 接口不可用，无法选择目录。')
      return
    }
    setBaseDirLoading(true)
    try {
      const res = await api.choose_directory(baseDir || undefined)
      if (!res?.success) {
        if (res?.message && res.message !== '未选择目录') {
          showMessage('error', res.message)
        }
        return
      }
      setBaseDir(res.data)
    } catch (err) {
      showMessage('error', err.message || '选择目录失败')
    } finally {
      setBaseDirLoading(false)
    }
  }, [api, baseDir, showMessage])

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#f5f5f5',
        padding: 24,
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          maxWidth: 1200,
          margin: '0 auto',
        }}
      >
        <Card
          style={{ width: '100%' }}
          bodyStyle={{ padding: 28 }}
        >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={3} style={{ marginBottom: 8 }}>
              自动截图器
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              选择一个正在运行的窗口，点击“开始截屏”即可按固定间隔保存图片。
            </Paragraph>
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
                placeholder="请选择要截屏的窗口"
                options={options}
                loading={loadingApps}
                value={selectedHwnd}
                onChange={setSelectedHwnd}
                showSearch
                optionFilterProp="keywords"
                optionLabelProp="label"
                notFoundContent="暂无可用窗口"
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
                刷新
              </Button>
              <Button
                size="large"
                onClick={() => fetchPreview(selectedHwnd)}
                loading={previewLoading}
                disabled={!selectedHwnd}
              >
                刷新预览
              </Button>
            </div>

            <div
              style={{
                display: 'flex',
                gap: 12,
                alignItems: 'center',
                flexWrap: 'wrap',
                flexGrow: 1,
              }}
            >
              <Text style={{ minWidth: 96, whiteSpace: 'nowrap' }}>截图间隔（秒）</Text>
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
                停止后生成 MP4
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
              <Text style={{ minWidth: 96, whiteSpace: 'nowrap' }}>保存目录</Text>
              <Input
                size="large"
                readOnly
                value={baseDir}
                placeholder="选择截屏保存目录"
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
                浏览...
              </Button>
            </div>
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
                type="primary"
                size="large"
                onClick={handleStart}
                disabled={!selectedHwnd || capturing}
              >
                开始截屏
              </Button>
              <Button
                danger
                size="large"
                onClick={handleStop}
                disabled={!capturing}
              >
                停止
              </Button>
            </Space>
            <Text type="secondary" style={{ whiteSpace: 'nowrap' }}>
              已截：{captureCount} 张
            </Text>
          </div>

          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {detailLines ? (
              <Card size="small" style={{ width: '100%' }}>
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Text strong style={{ fontSize: 16 }}>
                    {detailLines.title}
                  </Text>
                  <Space wrap>
                    <Text type="secondary">进程：{detailLines.process}</Text>
                    <Text type="secondary">句柄：{detailLines.hwndHex}</Text>
                    {detailLines.sizeLine ? (
                      <Text type="secondary">尺寸：{detailLines.sizeLine}</Text>
                    ) : null}
                  </Space>
                </Space>
              </Card>
            ) : null}

            <Card
              size="small"
              style={{ width: '100%' }}
              bodyStyle={{ padding: 12 }}
              title="预览"
              extra={previewLoading ? '加载中…' : null}
            >
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
                    alt="窗口预览"
                    style={{ maxWidth: '100%', maxHeight: 300, objectFit: 'contain' }}
                    preview={{ mask: '点击查看原图' }}
                  />
                </div>
              ) : (
                <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  选择窗口后显示最新截图。
                </Paragraph>
              )}
            </Card>
          </Space>

          {statusAlert}
        </Space>
        </Card>
      </div>
    </div>
  )
}
