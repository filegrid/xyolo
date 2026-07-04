import {
  BarChart3,
  Boxes,
  Brain,
  ChevronDown,
  ChevronRight,
  Database,
  Ellipsis,
  FolderOpen,
  Globe,
  Languages,
  Monitor,
  MoonStar,
  Pencil,
  Play,
  Plus,
  Save,
  Sun,
  TerminalSquare,
  Upload,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

type Section = 'dataset' | 'train' | 'model' | 'eval' | 'deploy'
type TrainView = 'new' | 'list' | 'template'
type Mode = 'venv' | 'docker'
type ThemeChoice = 'system' | 'light' | 'dark'
type Language = 'zh' | 'en'
type ActionType = 'launch' | 'save_draft' | 'save_template'

type EnvironmentPackage = {
  name: string
  version: string
}

type DockerImageStatus = {
  purpose: string
  image: string
  status: string
}

type EnvironmentDetails = {
  python_version: string
  project_tree: string
  docker_images: DockerImageStatus[]
  packages: EnvironmentPackage[]
}

type SummaryItem = {
  id: string
  name: string
  created_at: string
  updated_at?: string
  status?: string
  log_path?: string
}

type BootstrapPayload = {
  models: string[]
  datasets: string[]
  configs: string[]
  tools: Array<{
    name: 'dstack' | 'swanlab'
    display_name: string
    available: boolean
    url: string
    reason: string
  }>
  drafts: SummaryItem[]
  templates: SummaryItem[]
  tasks: SummaryItem[]
}

type RecordPayload = {
  ok: boolean
  item: {
    id: string
    name: string
    form: TaskForm
  }
}

type TaskForm = {
  name: string
  mode: Mode
  model: string
  data: string
  epochs: string
  batch: string
  imgsz: string
  device: string
  workers: string
  optimizer: string
  resume: string
  cache: string
  patience: string
  config_file: string
  config_text: string
  extra_args: string
  notes: string
}

type ParamDefinition = {
  key: string
  descriptionZh: string
  descriptionEn: string
  placeholder: string
  common?: boolean
}

const SECTION_OPTIONS = [
  { value: 'dataset', labelZh: '数据集', labelEn: 'Datasets', icon: Database },
  { value: 'train', labelZh: '训练', labelEn: 'Training', icon: Boxes },
  { value: 'model', labelZh: '模型', labelEn: 'Models', icon: Brain },
  { value: 'eval', labelZh: '评估', labelEn: 'Evaluation', icon: BarChart3 },
  { value: 'deploy', labelZh: '部署', labelEn: 'Deploy', icon: Upload },
] as const

const TRAIN_VIEW_OPTIONS = [
  { value: 'new', labelZh: '新建', labelEn: 'New' },
  { value: 'list', labelZh: '列表', labelEn: 'List' },
  { value: 'template', labelZh: '模板', labelEn: 'Template' },
] as const

const PARAM_DEFINITIONS: ParamDefinition[] = [
  { key: 'epochs', descriptionZh: '训练轮数', descriptionEn: 'Training epochs', placeholder: '200', common: true },
  { key: 'batch', descriptionZh: '批大小', descriptionEn: 'Batch size', placeholder: '8', common: true },
  { key: 'imgsz', descriptionZh: '输入尺寸', descriptionEn: 'Input image size', placeholder: '640', common: true },
  { key: 'lr0', descriptionZh: '初始学习率', descriptionEn: 'Initial learning rate', placeholder: '0.01', common: true },
  { key: 'optimizer', descriptionZh: '优化器', descriptionEn: 'Optimizer', placeholder: 'auto / SGD / AdamW', common: true },
  { key: 'device', descriptionZh: '训练设备', descriptionEn: 'Training device', placeholder: '0 / 0,1 / cpu', common: true },
  { key: 'workers', descriptionZh: '数据加载线程数', descriptionEn: 'Data loader workers', placeholder: '8', common: true },
  { key: 'patience', descriptionZh: '早停耐心值', descriptionEn: 'Early stop patience', placeholder: '50', common: true },
  { key: 'cache', descriptionZh: '缓存模式', descriptionEn: 'Caching mode', placeholder: 'true / ram / disk', common: true },
  { key: 'resume', descriptionZh: '断点续训', descriptionEn: 'Resume training', placeholder: 'true / checkpoint.pt', common: true },
  { key: 'lrf', descriptionZh: '最终学习率倍率', descriptionEn: 'Final LR factor', placeholder: '0.01' },
  { key: 'momentum', descriptionZh: '动量', descriptionEn: 'Momentum', placeholder: '0.937' },
  { key: 'weight_decay', descriptionZh: '权重衰减', descriptionEn: 'Weight decay', placeholder: '0.0005' },
  { key: 'warmup_epochs', descriptionZh: '预热轮数', descriptionEn: 'Warmup epochs', placeholder: '3.0' },
  { key: 'close_mosaic', descriptionZh: '最后多少轮关闭 Mosaic', descriptionEn: 'Disable mosaic in final epochs', placeholder: '10' },
  { key: 'cos_lr', descriptionZh: '余弦学习率', descriptionEn: 'Cosine LR schedule', placeholder: 'true' },
  { key: 'degrees', descriptionZh: '旋转增强角度', descriptionEn: 'Rotation augmentation', placeholder: '0.0' },
  { key: 'translate', descriptionZh: '平移增强', descriptionEn: 'Translation augmentation', placeholder: '0.1' },
  { key: 'scale', descriptionZh: '缩放增强', descriptionEn: 'Scale augmentation', placeholder: '0.5' },
  { key: 'fliplr', descriptionZh: '左右翻转概率', descriptionEn: 'Horizontal flip ratio', placeholder: '0.5' },
  { key: 'mosaic', descriptionZh: 'Mosaic 概率', descriptionEn: 'Mosaic probability', placeholder: '1.0' },
  { key: 'mixup', descriptionZh: 'MixUp 概率', descriptionEn: 'MixUp probability', placeholder: '0.0' },
  { key: 'copy_paste', descriptionZh: 'Copy-Paste 概率', descriptionEn: 'Copy-paste probability', placeholder: '0.0' },
  { key: 'save_period', descriptionZh: '保存周期', descriptionEn: 'Checkpoint save period', placeholder: '10' },
  { key: 'val', descriptionZh: '是否验证', descriptionEn: 'Run validation', placeholder: 'true' },
  { key: 'amp', descriptionZh: '自动混合精度', descriptionEn: 'Automatic mixed precision', placeholder: 'true' },
  { key: 'pretrained', descriptionZh: '是否使用预训练', descriptionEn: 'Use pretrained weights', placeholder: 'true' },
  { key: 'freeze', descriptionZh: '冻结层数', descriptionEn: 'Freeze layers', placeholder: '10' },
]

const DEFAULT_FORM: TaskForm = {
  name: '',
  mode: 'venv',
  model: '',
  data: '',
  epochs: '',
  batch: '',
  imgsz: '',
  device: '',
  workers: '',
  optimizer: '',
  resume: '',
  cache: '',
  patience: '',
  config_file: '',
  config_text: '',
  extra_args: '',
  notes: '',
}

const I18N = {
  zh: {
    title: 'XYolo',
    loading: '加载中...',
    train: '训练',
    datasets: '数据集',
    models: '模型',
    evaluation: '评估',
    deploy: '部署',
    new: '新建',
    list: '列表',
    template: '模板',
    name: '名字（自动生成）',
    notes: '备注',
    model: '模型',
    dataset: '数据集',
    modelHint: '可直接输入，也可从本地候选里下拉选择。',
    datasetHint: '可直接输入，也可从 datasets/ 里的候选下拉选择。',
    paramTitle: '指标参数',
    common: '常用',
    advancedParams: '高级',
    edit: '编辑',
    table: '表格',
    param: '参数',
    value: '值',
    description: '说明',
    importTemplate: '从模板导入',
    chooseTemplate: '选择模板',
    noSelection: '未选择',
    loadTemplate: '载入模板',
    noTemplates: '暂无模板',
    saveDraft: '暂存',
    saveTemplate: '保存模板',
    launch: '启动',
    save: '保存',
    mode: '模式',
    envTitle: '环境信息',
    envHint: '项目树、Docker 镜像、主要安装包都放这里。',
    pythonVersion: 'Python 版本',
    projectTree: '项目目录树',
    dockerImages: 'Docker Images',
    packageList: '安装包列表',
    purpose: '用途',
    image: '镜像',
    imageStatus: '状态',
    envLoading: '正在读取环境信息...',
    noTasks: '暂无任务',
    noModels: '暂无模型',
    noDatasets: '暂无数据集',
    createdAt: '创建时间',
    status: '状态',
    log: '日志',
    use: '使用',
    language: '语言',
    theme: '主题',
    system: '跟随系统',
    light: '浅色',
    dark: '深色',
    env: '环境信息',
    dstack: 'dstack',
    swanlab: 'SwanLab',
    toolTrying: '正在尝试拉起服务...',
    toolReady: '服务已就绪，正在打开。',
    toolUnavailable: '当前入口不可用',
    comingSoon: '该大类后续再补，现在先保留结构。',
  },
  en: {
    title: 'XYolo',
    loading: 'Loading...',
    train: 'Training',
    datasets: 'Datasets',
    models: 'Models',
    evaluation: 'Evaluation',
    deploy: 'Deploy',
    new: 'New',
    list: 'List',
    template: 'Template',
    name: 'Name (auto-generated)',
    notes: 'Notes',
    model: 'Model',
    dataset: 'Dataset',
    modelHint: 'Type directly or choose from local suggestions.',
    datasetHint: 'Type directly or choose from suggestions found in datasets/.',
    paramTitle: 'Parameter metrics',
    common: 'Common',
    advancedParams: 'Advanced',
    edit: 'Edit',
    table: 'Table',
    param: 'Parameter',
    value: 'Value',
    description: 'Description',
    importTemplate: 'Import from template',
    chooseTemplate: 'Choose template',
    noSelection: 'No selection',
    loadTemplate: 'Load template',
    noTemplates: 'No templates yet.',
    saveDraft: 'Save draft',
    saveTemplate: 'Save template',
    launch: 'Launch',
    save: 'Save',
    mode: 'Mode',
    envTitle: 'Environment',
    envHint: 'Project tree, Docker images, and main packages live here.',
    pythonVersion: 'Python version',
    projectTree: 'Project tree',
    dockerImages: 'Docker images',
    packageList: 'Installed packages',
    purpose: 'Purpose',
    image: 'Image',
    imageStatus: 'Status',
    envLoading: 'Loading environment details...',
    noTasks: 'No tasks yet.',
    noModels: 'No models yet.',
    noDatasets: 'No datasets yet.',
    createdAt: 'Created at',
    status: 'Status',
    log: 'Log',
    use: 'Use',
    language: 'Language',
    theme: 'Theme',
    system: 'System',
    light: 'Light',
    dark: 'Dark',
    env: 'Environment',
    dstack: 'dstack',
    swanlab: 'SwanLab',
    toolTrying: 'Trying to start the service...',
    toolReady: 'Service is ready and opening now.',
    toolUnavailable: 'This entry is unavailable.',
    comingSoon: 'This category is reserved for later.',
  },
} as const

function getCookie(name: string): string {
  const match = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : ''
}

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=31536000; samesite=lax`
}

function resolveTheme(choice: ThemeChoice): 'light' | 'dark' {
  if (choice === 'light' || choice === 'dark') {
    return choice
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function generateName() {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `xyolo-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

function parseYamlText(text: string): Record<string, string> {
  const next: Record<string, string> = {}
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#') || !line.includes(':')) continue
    const index = line.indexOf(':')
    const key = line.slice(0, index).trim()
    const value = line.slice(index + 1).trim()
    if (key) next[key] = value
  }
  return next
}

function buildYamlText(values: Record<string, string>, keys: string[]) {
  return keys
    .map((key) => {
      const value = (values[key] ?? '').trim()
      return value ? `${key}: ${value}` : ''
    })
    .filter(Boolean)
    .join('\n')
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.message || 'Request failed')
  return payload as T
}

function App() {
  const [lang, setLang] = useState<Language>(() => (getCookie('xyolo-lang') === 'en' ? 'en' : 'zh'))
  const [themeChoice, setThemeChoice] = useState<ThemeChoice>(() => {
    const cookie = getCookie('xyolo-theme')
    return cookie === 'light' || cookie === 'dark' || cookie === 'system' ? cookie : 'system'
  })
  const [section, setSection] = useState<Section>('train')
  const [trainView, setTrainView] = useState<TrainView>('new')
  const [bootstrap, setBootstrap] = useState<BootstrapPayload | null>(null)
  const [environmentDetails, setEnvironmentDetails] = useState<EnvironmentDetails | null>(null)
  const [environmentOpen, setEnvironmentOpen] = useState(false)
  const [environmentLoading, setEnvironmentLoading] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [langMenuOpen, setLangMenuOpen] = useState(false)
  const [themeMenuOpen, setThemeMenuOpen] = useState(false)
  const [commonParamMenuOpen, setCommonParamMenuOpen] = useState(false)
  const [advancedParamMenuOpen, setAdvancedParamMenuOpen] = useState(false)
  const [textMode, setTextMode] = useState(false)
  const [yamlText, setYamlText] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [toast, setToast] = useState('')
  const [busyAction, setBusyAction] = useState<ActionType | ''>('')
  const [form, setForm] = useState<TaskForm>({ ...DEFAULT_FORM, name: generateName() })
  const [selectedParamKeys, setSelectedParamKeys] = useState<string[]>(['epochs', 'batch', 'imgsz'])
  const [paramValues, setParamValues] = useState<Record<string, string>>({ epochs: '200', batch: '8', imgsz: '640' })
  const [editingKey, setEditingKey] = useState('')
  const [editingDraftValue, setEditingDraftValue] = useState('')

  const text = I18N[lang]
  const currentSection = SECTION_OPTIONS.find((item) => item.value === section) ?? SECTION_OPTIONS[1]
  const CurrentSectionIcon = currentSection.icon
  const availableParams = useMemo(() => {
    return PARAM_DEFINITIONS.filter((item) => !selectedParamKeys.includes(item.key)).sort((left, right) => {
      if (left.common === right.common) return 0
      return left.common ? -1 : 1
    })
  }, [selectedParamKeys])
  const commonParams = availableParams.filter((item) => item.common)
  const advancedParams = availableParams.filter((item) => !item.common)

  const showToast = (message: string) => {
    setToast(message)
    window.clearTimeout((window as Window & { __xyoloToast?: number }).__xyoloToast)
    ;(window as Window & { __xyoloToast?: number }).__xyoloToast = window.setTimeout(() => setToast(''), 2800)
  }

  const setFormValue = <K extends keyof TaskForm>(key: K, value: TaskForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const reloadBootstrap = async () => {
    const payload = await fetchJson<BootstrapPayload>('/api/bootstrap')
    setBootstrap(payload)
  }

  const loadEnvironmentDetails = async () => {
    setEnvironmentLoading(true)
    try {
      const payload = await fetchJson<EnvironmentDetails>('/api/environment')
      setEnvironmentDetails(payload)
    } finally {
      setEnvironmentLoading(false)
    }
  }

  const syncStateFromRecord = (nextForm: TaskForm, preserveName: boolean) => {
    const yamlMap = parseYamlText(nextForm.config_text || '')
    const merged: Record<string, string> = {}
    for (const key of ['epochs', 'batch', 'imgsz', 'device', 'workers', 'optimizer', 'resume', 'cache', 'patience']) {
      const value = nextForm[key as keyof TaskForm]
      if (typeof value === 'string' && value.trim()) merged[key] = value
    }
    for (const [key, value] of Object.entries(yamlMap)) merged[key] = value
    const keys = Object.keys(merged)
    setSelectedParamKeys(keys.length > 0 ? keys : ['epochs', 'batch', 'imgsz'])
    setParamValues(keys.length > 0 ? merged : { epochs: '200', batch: '8', imgsz: '640' })
    setYamlText(buildYamlText(keys.length > 0 ? merged : { epochs: '200', batch: '8', imgsz: '640' }, keys.length > 0 ? keys : ['epochs', 'batch', 'imgsz']))
    setForm({
      ...nextForm,
      name: preserveName ? form.name : nextForm.name || generateName(),
      epochs: '',
      batch: '',
      imgsz: '',
      device: '',
      workers: '',
      optimizer: '',
      resume: '',
      cache: '',
      patience: '',
      config_text: '',
      config_file: '',
      extra_args: '',
    })
  }

  const loadRecord = async (kind: 'templates' | 'drafts', id: string) => {
    if (!id) return
    const payload = await fetchJson<RecordPayload>(`/api/records/${kind}/${id}`)
    syncStateFromRecord(payload.item.form, kind === 'templates')
    setTrainView('new')
    showToast(lang === 'en' ? 'Template loaded.' : '模板已载入。')
  }

  const ensureYamlState = () => {
    if (!textMode) return { keys: selectedParamKeys, values: paramValues }
    const parsed = parseYamlText(yamlText)
    const keys = Object.keys(parsed)
    const values = keys.length > 0 ? parsed : {}
    return { keys, values }
  }

  const buildSubmitForm = (): TaskForm => {
    const yamlState = ensureYamlState()
    return {
      ...form,
      config_file: '',
      extra_args: '',
      epochs: '',
      batch: '',
      imgsz: '',
      device: '',
      workers: '',
      optimizer: '',
      resume: '',
      cache: '',
      patience: '',
      config_text: buildYamlText(yamlState.values, yamlState.keys),
    }
  }

  const runAction = async (action: ActionType) => {
    try {
      setBusyAction(action)
      const payload = await fetchJson<{ ok: boolean; message: string }>('/api/actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, form: buildSubmitForm() }),
      })
      showToast(payload.message)
      await reloadBootstrap()
      setForm((current) => ({ ...current, name: generateName() }))
      if (action === 'launch') setTrainView('list')
      if (action === 'save_template') setTrainView('template')
    } catch (error) {
      showToast(error instanceof Error ? error.message : String(error))
    } finally {
      setBusyAction('')
    }
  }

  const openTool = async (toolName: 'dstack' | 'swanlab') => {
    try {
      showToast(text.toolTrying)
      const payload = await fetchJson<{ ok: boolean; url: string; message: string }>(`/api/tools/${toolName}/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      showToast(payload.message || text.toolReady)
      window.open(payload.url, '_blank', 'noopener,noreferrer')
      await reloadBootstrap()
    } catch (error) {
      showToast(error instanceof Error ? error.message : text.toolUnavailable)
    }
  }

  const addParam = (key: string) => {
    if (!key || selectedParamKeys.includes(key)) return
    const definition = PARAM_DEFINITIONS.find((item) => item.key === key)
    setEditingKey(key)
    setEditingDraftValue(definition?.placeholder ?? '')
    setCommonParamMenuOpen(false)
    setAdvancedParamMenuOpen(false)
  }

  const openEditParam = (key: string) => {
    setEditingKey(key)
    setEditingDraftValue(paramValues[key] ?? '')
  }

  const saveRowParam = (key: string) => {
    const nextKeys = selectedParamKeys.includes(key) ? selectedParamKeys : [...selectedParamKeys, key]
    const nextValues = { ...paramValues, [key]: editingDraftValue }
    setSelectedParamKeys(nextKeys)
    setParamValues(nextValues)
    setYamlText(buildYamlText(nextValues, nextKeys))
    setEditingKey('')
    setEditingDraftValue('')
  }

  const removeParam = (key: string) => {
    const nextKeys = selectedParamKeys.filter((item) => item !== key)
    const nextValues = { ...paramValues }
    delete nextValues[key]
    setSelectedParamKeys(nextKeys)
    setParamValues(nextValues)
    setYamlText(buildYamlText(nextValues, nextKeys))
    if (editingKey === key) {
      setEditingKey('')
      setEditingDraftValue('')
    }
  }

  useEffect(() => {
    setCookie('xyolo-lang', lang)
  }, [lang])

  useEffect(() => {
    document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN'
  }, [lang])

  useEffect(() => {
    document.documentElement.dataset.theme = resolveTheme(themeChoice)
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const listener = () => {
      if (themeChoice === 'system') document.documentElement.dataset.theme = resolveTheme('system')
    }
    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [themeChoice])

  useEffect(() => {
    setCookie('xyolo-theme', themeChoice)
  }, [themeChoice])

  useEffect(() => {
    reloadBootstrap().catch((error: Error) => showToast(error.message))
  }, [])

  useEffect(() => {
    if (!textMode) {
      setYamlText(buildYamlText(paramValues, selectedParamKeys))
    }
  }, [textMode])

  if (!bootstrap) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="w-full max-w-sm">
          <CardContent className="flex h-32 items-center justify-center text-sm text-muted-foreground">{text.loading}</CardContent>
        </Card>
      </div>
    )
  }

  const templates = bootstrap.templates ?? []

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <div className="mb-5 flex items-start justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{text.title}</h1>

        <div className="relative flex items-center gap-2">
          <div className="group relative">
            <button
              type="button"
              className="flex h-9 items-center gap-1 rounded-md border px-2.5 text-sm hover:bg-accent"
              aria-label={text.language}
              onClick={() => {
                setLangMenuOpen((current) => !current)
                setThemeMenuOpen(false)
                setMenuOpen(false)
              }}
            >
              {lang === 'en' ? <Globe className="size-4" /> : <Languages className="size-4" />}
              <ChevronDown className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
            {langMenuOpen ? (
              <div className="absolute right-0 top-11 z-40 min-w-32 rounded-lg border bg-background p-1 shadow-lg">
                <button type="button" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent" onClick={() => { setLang('zh'); setLangMenuOpen(false) }}>
                  <Languages className="size-4" />
                  中文
                </button>
                <button type="button" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent" onClick={() => { setLang('en'); setLangMenuOpen(false) }}>
                  <Globe className="size-4" />
                  English
                </button>
              </div>
            ) : null}
          </div>

          <div className="group relative">
            <button
              type="button"
              className="flex h-9 items-center gap-1 rounded-md border px-2.5 text-sm hover:bg-accent"
              aria-label={text.theme}
              onClick={() => {
                setThemeMenuOpen((current) => !current)
                setLangMenuOpen(false)
                setMenuOpen(false)
              }}
            >
              {themeChoice === 'light' ? <Sun className="size-4" /> : themeChoice === 'dark' ? <MoonStar className="size-4" /> : <Monitor className="size-4" />}
              <ChevronDown className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
            {themeMenuOpen ? (
              <div className="absolute right-0 top-11 z-40 min-w-36 rounded-lg border bg-background p-1 shadow-lg">
                <button type="button" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent" onClick={() => { setThemeChoice('system'); setThemeMenuOpen(false) }}>
                  <Monitor className="size-4" />
                  {text.system}
                </button>
                <button type="button" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent" onClick={() => { setThemeChoice('light'); setThemeMenuOpen(false) }}>
                  <Sun className="size-4" />
                  {text.light}
                </button>
                <button type="button" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent" onClick={() => { setThemeChoice('dark'); setThemeMenuOpen(false) }}>
                  <MoonStar className="size-4" />
                  {text.dark}
                </button>
              </div>
            ) : null}
          </div>

          <Button variant="outline" size="icon" onClick={() => setMenuOpen((current) => !current)} aria-label="menu">
            <Ellipsis className="size-4" />
          </Button>

          {menuOpen ? (
            <div className="absolute right-0 top-11 z-40 min-w-44 rounded-lg border bg-background p-1 shadow-lg">
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                onClick={() => {
                  setMenuOpen(false)
                  setEnvironmentOpen(true)
                  if (!environmentDetails && !environmentLoading) {
                    loadEnvironmentDetails().catch((error: Error) => showToast(error.message))
                  }
                }}
              >
                <TerminalSquare className="size-4" />
                {text.env}
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                onClick={() => {
                  setMenuOpen(false)
                  openTool('dstack').catch(() => undefined)
                }}
              >
                <Globe className="size-4" />
                {text.dstack}
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                onClick={() => {
                  setMenuOpen(false)
                  openTool('swanlab').catch(() => undefined)
                }}
              >
                <Globe className="size-4" />
                {text.swanlab}
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <Dialog open={environmentOpen} onOpenChange={setEnvironmentOpen}>
        <DialogTrigger asChild>
          <span className="hidden" />
        </DialogTrigger>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>{text.envTitle}</DialogTitle>
            <DialogDescription>{text.envHint}</DialogDescription>
          </DialogHeader>

          {environmentLoading || !environmentDetails ? (
            <div className="py-8 text-sm text-muted-foreground">{text.envLoading}</div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="text-xs text-muted-foreground">{text.pythonVersion}</div>
                <div className="mt-1 text-sm font-medium">{environmentDetails.python_version}</div>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium">{text.projectTree}</div>
                <pre className="overflow-x-auto rounded-lg border bg-muted/30 p-4 font-mono text-xs leading-6">{environmentDetails.project_tree}</pre>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium">{text.dockerImages}</div>
                <div className="overflow-hidden rounded-lg border">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-muted/50 text-left text-muted-foreground">
                        <tr>
                          <th className="px-4 py-3 font-medium">{text.purpose}</th>
                          <th className="px-4 py-3 font-medium">{text.image}</th>
                          <th className="px-4 py-3 font-medium">{text.imageStatus}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {environmentDetails.docker_images.map((item) => (
                          <tr key={`${item.purpose}-${item.image}`} className="border-t">
                            <td className="px-4 py-2 font-medium">{item.purpose}</td>
                            <td className="px-4 py-2 font-mono text-xs">{item.image}</td>
                            <td className="px-4 py-2 text-muted-foreground">{item.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <Collapsible className="rounded-lg border">
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" className="flex h-auto w-full items-center justify-between rounded-lg p-4">
                    <span className="font-medium">{`${text.packageList} (${environmentDetails.packages.length})`}</span>
                    <Pencil className="size-4" />
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="border-t">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-left text-muted-foreground">
                      <tr>
                        <th className="px-4 py-3 font-medium">{lang === 'en' ? 'Package' : '包名'}</th>
                        <th className="px-4 py-3 font-medium">{lang === 'en' ? 'Version' : '版本'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {environmentDetails.packages.map((item) => (
                        <tr key={item.name} className="border-t">
                          <td className="px-4 py-2 font-medium">{item.name}</td>
                          <td className="px-4 py-2 text-muted-foreground">{item.version}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CollapsibleContent>
              </Collapsible>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Select value={section} onValueChange={(value) => setSection(value as Section)}>
          <SelectTrigger className="h-10 w-[180px]">
            <div className="flex items-center gap-2">
              <CurrentSectionIcon className="size-4" />
              <span>{lang === 'en' ? currentSection.labelEn : currentSection.labelZh}</span>
            </div>
          </SelectTrigger>
          <SelectContent>
            {SECTION_OPTIONS.map((item) => {
              const Icon = item.icon
              return (
                <SelectItem key={item.value} value={item.value}>
                  <div className="flex items-center gap-2">
                    <Icon className="size-4" />
                    {lang === 'en' ? item.labelEn : item.labelZh}
                  </div>
                </SelectItem>
              )
            })}
          </SelectContent>
        </Select>

        {section === 'train' ? (
          <>
            <ChevronRight className="size-4 text-muted-foreground" />
            <div className="inline-flex rounded-lg border bg-muted/40 p-1">
              {TRAIN_VIEW_OPTIONS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  className={`rounded-md px-3 py-1.5 text-sm ${trainView === item.value ? 'bg-background shadow-sm' : 'text-muted-foreground'}`}
                  onClick={() => setTrainView(item.value as TrainView)}
                >
                  {lang === 'en' ? item.labelEn : item.labelZh}
                </button>
              ))}
            </div>
          </>
        ) : null}
      </div>

      {section === 'dataset' ? (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr><th className="px-4 py-3 font-medium">{lang === 'en' ? 'Name' : '名称'}</th></tr>
            </thead>
            <tbody>
              {bootstrap.datasets.length === 0 ? <tr><td className="px-4 py-6 text-muted-foreground">{text.noDatasets}</td></tr> : bootstrap.datasets.map((item) => <tr key={item} className="border-t"><td className="px-4 py-3 font-medium">{item}</td></tr>)}
            </tbody>
          </table>
        </div>
      ) : null}

      {section === 'model' ? (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr><th className="px-4 py-3 font-medium">{lang === 'en' ? 'Name' : '名称'}</th></tr>
            </thead>
            <tbody>
              {bootstrap.models.length === 0 ? <tr><td className="px-4 py-6 text-muted-foreground">{text.noModels}</td></tr> : bootstrap.models.map((item) => <tr key={item} className="border-t"><td className="px-4 py-3 font-medium">{item}</td></tr>)}
            </tbody>
          </table>
        </div>
      ) : null}

      {section === 'eval' || section === 'deploy' ? <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">{text.comingSoon}</div> : null}

      {section === 'train' && trainView === 'list' ? (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">{lang === 'en' ? 'Name' : '名称'}</th>
                <th className="px-4 py-3 font-medium">{text.status}</th>
                <th className="px-4 py-3 font-medium">{text.createdAt}</th>
                <th className="px-4 py-3 font-medium">{text.log}</th>
              </tr>
            </thead>
            <tbody>
              {bootstrap.tasks.length === 0 ? (
                <tr><td className="px-4 py-6 text-muted-foreground" colSpan={4}>{text.noTasks}</td></tr>
              ) : (
                bootstrap.tasks.map((item) => (
                  <tr key={item.id} className="border-t">
                    <td className="px-4 py-3 font-medium">{item.name}</td>
                    <td className="px-4 py-3">{item.status || '-'}</td>
                    <td className="px-4 py-3 text-muted-foreground">{item.created_at}</td>
                    <td className="px-4 py-3">{item.log_path ? <a className="text-primary hover:underline" href={`/logs?id=${item.id}`} target="_blank" rel="noreferrer">{text.log}</a> : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {section === 'train' && trainView === 'template' ? (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">{lang === 'en' ? 'Name' : '名称'}</th>
                <th className="px-4 py-3 font-medium">{text.createdAt}</th>
                <th className="px-4 py-3 font-medium">{text.use}</th>
              </tr>
            </thead>
            <tbody>
              {templates.length === 0 ? (
                <tr><td className="px-4 py-6 text-muted-foreground" colSpan={3}>{text.noTemplates}</td></tr>
              ) : (
                templates.map((item) => (
                  <tr key={item.id} className="border-t">
                    <td className="px-4 py-3 font-medium">{item.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{item.updated_at || item.created_at}</td>
                    <td className="px-4 py-3">
                      <button type="button" className="text-primary hover:underline" onClick={() => loadRecord('templates', item.id).catch((error: Error) => showToast(error.message))}>{text.use}</button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {section === 'train' && trainView === 'new' ? (
        <Card>
          <CardContent className="space-y-5 pt-6">
            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
              <div className="space-y-2">
                <label className="text-sm font-medium">{text.name}</label>
                <Input value={form.name} readOnly />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{text.notes}</label>
                <Input value={form.notes} onChange={(event) => setFormValue('notes', event.target.value)} />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">{text.model}</label>
                <Input value={form.model} onChange={(event) => setFormValue('model', event.target.value)} list="model-options" placeholder="best.pt / yolov8s.pt / ./other/model.pt" />
                <p className="text-xs text-muted-foreground">{text.modelHint}</p>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{text.dataset}</label>
                <Input value={form.data} onChange={(event) => setFormValue('data', event.target.value)} list="dataset-options" placeholder="my_dataset.yaml / ./other/data.yaml" />
                <p className="text-xs text-muted-foreground">{text.datasetHint}</p>
              </div>
            </div>

            <datalist id="model-options">
              {bootstrap.models.map((item) => <option key={item} value={item} />)}
            </datalist>
            <datalist id="dataset-options">
              {bootstrap.datasets.map((item) => <option key={item} value={item} />)}
            </datalist>

            <div className="space-y-4 rounded-xl border p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="font-medium">{text.paramTitle}</div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Button variant="outline" size="sm" onClick={() => { setCommonParamMenuOpen((current) => !current); setAdvancedParamMenuOpen(false) }}>
                      <Plus className="size-4" />
                      {text.common}
                    </Button>
                    {commonParamMenuOpen ? (
                      <div className="absolute right-0 top-10 z-30 max-h-80 min-w-72 overflow-y-auto rounded-lg border bg-background p-1 shadow-lg">
                        {commonParams.length === 0 ? (
                          <div className="px-3 py-2 text-sm text-muted-foreground">-</div>
                        ) : (
                          commonParams.map((item) => (
                            <button
                              key={item.key}
                              type="button"
                              className="flex w-full flex-col rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                              onClick={() => addParam(item.key)}
                            >
                              <span className="font-medium">{item.key}</span>
                              <span className="text-xs text-muted-foreground">{lang === 'en' ? item.descriptionEn : item.descriptionZh}</span>
                            </button>
                          ))
                        )}
                      </div>
                    ) : null}
                  </div>
                  <div className="relative">
                    <Button variant="outline" size="sm" onClick={() => { setAdvancedParamMenuOpen((current) => !current); setCommonParamMenuOpen(false) }}>
                      <Plus className="size-4" />
                      {text.advancedParams}
                    </Button>
                    {advancedParamMenuOpen ? (
                      <div className="absolute right-0 top-10 z-30 max-h-80 min-w-72 overflow-y-auto rounded-lg border bg-background p-1 shadow-lg">
                        {advancedParams.length === 0 ? (
                          <div className="px-3 py-2 text-sm text-muted-foreground">-</div>
                        ) : (
                          advancedParams.map((item) => (
                            <button
                              key={item.key}
                              type="button"
                              className="flex w-full flex-col rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                              onClick={() => addParam(item.key)}
                            >
                              <span className="font-medium">{item.key}</span>
                              <span className="text-xs text-muted-foreground">{lang === 'en' ? item.descriptionEn : item.descriptionZh}</span>
                            </button>
                          ))
                        )}
                      </div>
                    ) : null}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (textMode) {
                        const parsed = parseYamlText(yamlText)
                        const keys = Object.keys(parsed)
                        setSelectedParamKeys(keys)
                        setParamValues(parsed)
                      } else {
                        setYamlText(buildYamlText(paramValues, selectedParamKeys))
                      }
                      setTextMode((current) => !current)
                    }}
                  >
                    <Pencil className="size-4" />
                    {textMode ? text.table : text.edit}
                  </Button>
                </div>
              </div>

              {textMode ? (
                <Textarea value={yamlText} onChange={(event) => setYamlText(event.target.value)} className="min-h-[260px] font-mono" />
              ) : (
                <>
                  <div className="flex flex-wrap gap-2">
                    {selectedParamKeys.map((key) => (
                      <span key={key} className="inline-flex items-center gap-1 rounded-full border bg-muted/30 px-3 py-1 text-xs font-medium">
                        <button type="button" className="hover:text-primary" onClick={() => openEditParam(key)}>
                          {`${key}=${paramValues[key] ?? ''}`}
                        </button>
                        <button type="button" className="rounded-full p-0.5 hover:bg-background" onClick={() => removeParam(key)}>
                          <X className="size-3" />
                        </button>
                      </span>
                    ))}
                  </div>

                  {editingKey ? (
                    <div className="overflow-hidden rounded-lg border">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50 text-left text-muted-foreground">
                          <tr>
                            <th className="px-4 py-3 font-medium">{text.param}</th>
                            <th className="px-4 py-3 font-medium">{text.value}</th>
                            <th className="px-4 py-3 font-medium">{text.description}</th>
                            <th className="px-4 py-3 font-medium"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {(() => {
                          const definition = PARAM_DEFINITIONS.find((item) => item.key === editingKey)
                          const savedValue = paramValues[editingKey] ?? ''
                          const dirty = editingDraftValue !== savedValue
                          return (
                            <tr key={editingKey} className="border-t">
                              <td className="px-4 py-3 font-medium">{editingKey}</td>
                              <td className="px-4 py-2">
                                <Input
                                  value={editingDraftValue}
                                  placeholder={definition?.placeholder ?? ''}
                                  onChange={(event) => setEditingDraftValue(event.target.value)}
                                />
                              </td>
                              <td className="px-4 py-3 text-muted-foreground">{lang === 'en' ? definition?.descriptionEn : definition?.descriptionZh}</td>
                              <td className="px-4 py-2 text-right">
                                <div className="flex justify-end gap-2">
                                  <Button size="sm" variant="outline" onClick={() => removeParam(editingKey)}>
                                    {lang === 'en' ? 'Remove' : '删除'}
                                  </Button>
                                  <Button size="sm" variant="outline" disabled={!dirty} onClick={() => saveRowParam(editingKey)}>
                                    {text.save}
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          )
                        })()}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </>
              )}
            </div>

            <div className="flex items-center justify-between gap-4">
              <Dialog>
                <DialogTrigger asChild>
                  <button type="button" className="text-sm font-medium text-primary hover:underline">
                    {text.importTemplate}
                  </button>
                </DialogTrigger>
                <DialogContent className="max-w-md">
                  <DialogHeader>
                    <DialogTitle>{text.importTemplate}</DialogTitle>
                    <DialogDescription>{text.chooseTemplate}</DialogDescription>
                  </DialogHeader>
                  {templates.length === 0 ? (
                    <div className="text-sm text-muted-foreground">{text.noTemplates}</div>
                  ) : (
                    <div className="space-y-3">
                      <Select value={selectedTemplateId} onValueChange={setSelectedTemplateId}>
                        <SelectTrigger>
                          <span>{selectedTemplateId ? templates.find((item) => item.id === selectedTemplateId)?.name : text.noSelection}</span>
                        </SelectTrigger>
                        <SelectContent>
                          {templates.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      <Button className="w-full" onClick={() => loadRecord('templates', selectedTemplateId)} disabled={!selectedTemplateId}>
                        <FolderOpen className="size-4" />
                        {text.loadTemplate}
                      </Button>
                    </div>
                  )}
                </DialogContent>
              </Dialog>

              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => runAction('save_draft')} disabled={busyAction !== ''}>
                  <Save className="size-4" />
                  {busyAction === 'save_draft' ? `${text.saveDraft}...` : text.saveDraft}
                </Button>
                <Button variant="outline" size="sm" onClick={() => runAction('save_template')} disabled={busyAction !== ''}>
                  <Save className="size-4" />
                  {busyAction === 'save_template' ? `${text.saveTemplate}...` : text.saveTemplate}
                </Button>
                <Button size="sm" onClick={() => runAction('launch')} disabled={busyAction !== ''}>
                  <Play className="size-4" />
                  {busyAction === 'launch' ? `${text.launch}...` : text.launch}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {toast ? <div className="fixed bottom-4 right-4 z-50 max-w-sm rounded-lg border bg-background px-4 py-3 text-sm shadow-lg">{toast}</div> : null}
    </div>
  )
}

export default App
