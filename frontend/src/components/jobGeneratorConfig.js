/** Shared purpose/generator/model options for job authoring UIs. */

export const JOB_PURPOSES = ['imagecontent', 'videocontent']

export const GENERATORS_BY_PURPOSE = {
  imagecontent: ['dalle', 'gptimage15', 'gptimage2'],
  videocontent: ['runway-video'],
}

export const RUNWAY_VIDEO_MODELS = ['gen4_turbo', 'veo3.1_fast']

export const DEFAULT_NEW_JOB_BY_PURPOSE = {
  imagecontent: {
    generator: 'dalle',
    purpose: 'imagecontent',
    promptText: '',
  },
  videocontent: {
    generator: 'runway-video',
    purpose: 'videocontent',
    promptText: '',
    model: 'gen4_turbo',
    imageSlot: null,
  },
}

export function generatorsForPurpose(purpose) {
  return GENERATORS_BY_PURPOSE[purpose] || GENERATORS_BY_PURPOSE.imagecontent
}

export function isRunwayGenerator(generator) {
  return (generator || '').toLowerCase() === 'runway-video'
}

export function defaultNewJob(purpose = 'imagecontent') {
  const base = DEFAULT_NEW_JOB_BY_PURPOSE[purpose] || DEFAULT_NEW_JOB_BY_PURPOSE.imagecontent
  return { ...base, order: 0 }
}

export function nextDraftReferenceId(jobs) {
  if (!Array.isArray(jobs) || jobs.length === 0) return 1
  const refs = jobs
    .map((job) => job?.reference_id)
    .filter((ref) => typeof ref === 'number' && ref >= 1)
  return refs.length ? Math.max(...refs) + 1 : 1
}

export function firstImageSlotReferenceId(jobs) {
  if (!Array.isArray(jobs)) return 1
  const imageJob = jobs.find(
    (job) =>
      job?.purpose === 'imagecontent' &&
      typeof job?.reference_id === 'number' &&
      job.reference_id >= 1
  )
  return imageJob?.reference_id ?? 1
}

export function imageSlotOptions(jobs) {
  if (!Array.isArray(jobs)) return []
  return jobs
    .filter(
      (job) =>
        job?.purpose === 'imagecontent' &&
        typeof job?.reference_id === 'number' &&
        job.reference_id >= 1
    )
    .map((job) => ({
      value: job.reference_id,
      label: `Ref ${job.reference_id} — ${job.generator || 'image'}`,
    }))
}

export function emptyDraftJob(purpose = 'imagecontent', siblingJobs = []) {
  const base = defaultNewJob(purpose)
  const reference_id = nextDraftReferenceId(siblingJobs)
  const imageSlot = firstImageSlotReferenceId(siblingJobs)
  return {
    generator: base.generator,
    purpose: base.purpose,
    reference_id,
    prompt: isRunwayGenerator(base.generator)
      ? { prompt: '', model: base.model, reference_id: imageSlot }
      : { prompt: '' },
    order: 0,
  }
}

export function runwayImageSlotValid(job, siblingJobs) {
  if (!isRunwayGenerator(job?.generator)) return true
  if (!Array.isArray(siblingJobs) || siblingJobs.length === 0) return false
  const referenceId = job?.prompt?.reference_id
  if (typeof referenceId !== 'number' || referenceId < 1) return false

  return siblingJobs.some(
    (siblingJob) =>
      siblingJob?.purpose === 'imagecontent' && siblingJob?.reference_id === referenceId
  )
}

export function draftJobPromptValid(job, siblingJobs = []) {
  if (!job?.generator) return false
  if (typeof job?.reference_id !== 'number' || job.reference_id < 1) return false
  const text = job?.prompt?.prompt
  if (typeof text !== 'string' || !text.trim()) return false
  if (isRunwayGenerator(job.generator)) {
    return Boolean(job.prompt?.model) && runwayImageSlotValid(job, siblingJobs)
  }
  return true
}
