import { useState, useEffect } from 'react';
import { generateOutline, generateSlidePlan, buildPresentation, getJobStatus, API_BASE_URL } from '../services/api';
import SlideEditor from '../components/SlideEditor';
import { Container, Title, Text, Button, Group, Loader, Alert, SimpleGrid, Stack, Stepper, Center, Card, Radio, Textarea, NumberInput } from '@mantine/core';
import { IconCircleCheck, IconAlertCircle, IconFileTypePdf, IconPhoto, IconBrain, IconSparkles, IconX } from '@tabler/icons-react';
import { FileDropzone } from '../components/FileDropzone';
import SortableImageList from '../components/SortableImageList';

const DEFAULT_SLIDE_COUNT = 8;

export default function CreatorPage() {
  const [activeStep, setActiveStep] = useState(0);
  const [sourceFile, setSourceFile] = useState(null);
  const [imageFiles, setImageFiles] = useState([]);

  const [workspaceId, setWorkspaceId] = useState('');
  const [outlineTaskId, setOutlineTaskId] = useState('');
  const [outlineStatus, setOutlineStatus] = useState('idle');
  const [outline, setOutline] = useState([]);
  const [sourceFilename, setSourceFilename] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [slideCount, setSlideCount] = useState(DEFAULT_SLIDE_COUNT);

  const [planTaskId, setPlanTaskId] = useState('');
  const [buildJobId, setBuildJobId] = useState('');
  const [slidePlan, setSlidePlan] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [finalUrl, setFinalUrl] = useState('');
  const [imageStrategy, setImageStrategy] = useState('uploaded');

  useEffect(() => {
    if (outlineStatus !== 'pending' || !outlineTaskId) return;

    const intervalId = setInterval(async () => {
      try {
        const statusResult = await getJobStatus(outlineTaskId);
        if (statusResult.status === 'SUCCESS') {
          clearInterval(intervalId);
          setOutline(statusResult.result?.outline ?? []);
          setOutlineStatus('ready');
        } else if (statusResult.status === 'FAILURE') {
          clearInterval(intervalId);
          setError('Failed to generate outline.');
          setOutlineStatus('error');
        }
      } catch (err) {
        clearInterval(intervalId);
        setError(err.message);
        setOutlineStatus('error');
      }
    }, 4000);

    return () => clearInterval(intervalId);
  }, [outlineStatus, outlineTaskId]);

  useEffect(() => {
    if (imageStrategy !== 'uploaded' && imageFiles.length > 0) {
      setImageFiles([]);
    }
  }, [imageStrategy]);

  useEffect(() => {
    if (status !== 'generating' && status !== 'building') return;

    const currentTaskId = status === 'generating' ? planTaskId : buildJobId;
    if (!currentTaskId) return;

    const intervalId = setInterval(async () => {
      try {
        const statusResult = await getJobStatus(currentTaskId);
        if (statusResult.status === 'SUCCESS') {
          clearInterval(intervalId);
          if (status === 'generating') {
            setSlidePlan(statusResult.result?.slide_plan ?? []);
            setStatus('review');
          } else {
            const downloadUrl = `${API_BASE_URL}/api/v1/creator/download/${workspaceId}`;
            setFinalUrl(downloadUrl);
            setStatus('complete');
          }
        } else if (statusResult.status === 'FAILURE') {
          clearInterval(intervalId);
          setError('An error occurred during backend processing.');
          setStatus('error');
        }
      } catch (err) {
        clearInterval(intervalId);
        setError(err.message);
        setStatus('error');
      }
    }, 5000);

    return () => clearInterval(intervalId);
  }, [status, planTaskId, buildJobId, workspaceId]);

  const resetWorkflow = () => {
    setImageFiles([]);
    setWorkspaceId('');
    setOutline([]);
    setOutlineTaskId('');
    setOutlineStatus('idle');
    setSourceFilename('');
    setSourceText('');
    setSlideCount(DEFAULT_SLIDE_COUNT);
    setPlanTaskId('');
    setBuildJobId('');
    setSlidePlan(null);
    setStatus('idle');
    setError('');
    setFinalUrl('');
    setActiveStep(0);
    setImageStrategy('uploaded');
  };

  const handleSourceSelect = (files) => {
    const file = files[0];
    if (!file) return;
    resetWorkflow();
    setSourceFile(file);
    setSourceFilename(file.name);
  };

  const handleClearSource = () => {
    setSourceFile(null);
    setSourceFilename('');
    setWorkspaceId('');
    setOutline([]);
    setOutlineTaskId('');
    setOutlineStatus('idle');
    setImageFiles([]);
    setPlanTaskId('');
    setBuildJobId('');
    setSlidePlan(null);
    setStatus('idle');
    setError('');
    setFinalUrl('');
    setActiveStep(0);
    setImageStrategy('uploaded');
  };

  const startOutlineGeneration = async () => {
    const trimmedText = sourceText.trim();
    if (!sourceFile && trimmedText.length === 0) {
      setError('Please upload a source document or paste source text.');
      return;
    }
    setError('');
    setOutline([]);
    setOutlineStatus('uploading');
    setImageFiles([]);
    setPlanTaskId('');
    setSlidePlan(null);
    setBuildJobId('');
    setFinalUrl('');
    setStatus('idle');
    setImageStrategy('uploaded');
    try {
      const response = await generateOutline({
        sourceFile,
        sourceText: trimmedText,
        slideCount,
      });
      setWorkspaceId(response.job_id);
      setOutlineTaskId(response.outline_task_id);
      setSourceFilename(response.source_filename ?? sourceFile?.name ?? 'pasted-text.txt');
      if (typeof response.slide_count === 'number') {
        setSlideCount(response.slide_count);
      }
      setOutlineStatus('pending');
    } catch (err) {
      setError(err.message);
      setOutlineStatus('error');
    }
  };

  const isNextDisabled = () => {
    if (activeStep === 0) return !sourceFile && sourceText.trim().length === 0;
    if (activeStep === 1) return outlineStatus !== 'ready';
    if (activeStep === 2 && imageStrategy === 'uploaded') return imageFiles.length === 0;
    return false;
  };

  const handleNext = () => {
    if (activeStep === 0) {
      if (!sourceFile) return;
      if (outlineStatus === 'idle' || outlineStatus === 'error') {
        startOutlineGeneration();
      }
      setActiveStep(1);
      return;
    }
    if (activeStep === 1 && outlineStatus !== 'ready') return;
    if (activeStep === 2 && imageStrategy === 'uploaded' && imageFiles.length === 0) return;
    setActiveStep((step) => Math.min(step + 1, 3));
  };

  const handleBack = () => {
    setActiveStep((step) => Math.max(step - 1, 0));
  };

  const handleGeneratePlan = async () => {
    if (!workspaceId) {
      setError('Generate an outline before creating the slide plan.');
      return;
    }
    if (imageStrategy === 'uploaded' && imageFiles.length === 0) {
      setError('Please upload at least one image.');
      return;
    }
    setStatus('generating');
    setError('');
    try {
      const result = await generateSlidePlan(workspaceId, imageFiles, imageStrategy);
      setPlanTaskId(result.plan_task_id);
      setWorkspaceId(result.job_id);
      if (result.image_strategy) {
        setImageStrategy(result.image_strategy);
      }
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const handleBuildPresentation = async () => {
    setStatus('building');
    try {
      const result = await buildPresentation(workspaceId, slidePlan);
      setBuildJobId(result.build_job_id);
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const handlePlanChange = (index, updatedSlide) => {
    const newPlan = [...slidePlan];
    newPlan[index] = updatedSlide;
    setSlidePlan(newPlan);
  };

  const handleReset = () => {
    resetWorkflow();
    setSourceFile(null);
  };

  if (status === 'review' || status === 'building' || status === 'complete') {
    return (
      <Container size="lg">
        <Stack gap="lg">
          <Title order={1} ta="center" mt="md">Review & Edit AI Plan</Title>
          <Text c="dimmed" ta="center" size="lg">
            Make any adjustments to the AI-generated content before building the final presentation.
          </Text>
          
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl" mt="md">
            {slidePlan && slidePlan.map((slide, index) => {
              const imageForSlide = imageFiles[index];
              const imageUrl = imageForSlide ? URL.createObjectURL(imageForSlide) : null;
              return (
                <SlideEditor 
                  key={index} 
                  slide={slide} 
                  index={index} 
                  imageUrl={imageUrl}
                  onUpdate={handlePlanChange} 
                />
              );
            })}
          </SimpleGrid>

          {status === 'review' && (
            <Group justify="center" mt="xl">
                <Button onClick={handleBuildPresentation} size="lg" loading={status === 'building'}>
                  Build Final Presentation
                </Button>
                <Button variant="default" onClick={handleReset}>Start Over</Button>
            </Group>
          )}
          
          {status === 'building' && (
            <Group justify="center" mt="xl"><Loader /><Text>Building presentation, please wait...</Text></Group>
          )}
          
          {status === 'complete' && (
            <Alert icon={<IconCircleCheck size="1rem" />} title="Build Complete!" color="teal" variant="light" radius="md">
                <Stack>
                    <Text>Your new presentation is ready for download.</Text>
                    <Button component="a" href={finalUrl} size="md" fullWidth>Download Presentation</Button>
                    <Button variant="default" onClick={handleReset}>Create Another</Button>
                </Stack>
            </Alert>
          )}
           {error && <Alert color="red" title="Error" mt="md" withCloseButton onClose={() => setError('')}>{error}</Alert>}
        </Stack>
      </Container>
    );
  }

  return (
    <Container size="md">
      <Stack gap="xl" align="center">
        <Stack gap="xs" align="center" mt="md">
          <Title order={1}>PPT Creator</Title>
          <Text c="dimmed" ta="center" size="lg">Follow the steps to generate a new presentation from your content.</Text>
        </Stack>

        <Stepper active={activeStep} allowNextStepsSelect={false} style={{ width: '100%' }} mt="lg">
          <Stepper.Step label="Step 1" description="Provide Source Material" icon={<IconFileTypePdf size={24} />}>
            <Card withBorder p="xl" radius="md" mt="xl">
              <Stack gap="lg">
                {!sourceFile ? (
                  <FileDropzone
                    onDrop={handleSourceSelect}
                    multiple={false}
                    fileType="doc"
                    title="Drag & drop source document"
                    subtitle="or click to select a PDF, DOCX, or TXT file"
                  />
                ) : (
                  <Stack align="center" gap="sm">
                    <IconCircleCheck size={48} color="var(--mantine-color-teal-5)" />
                    <Title order={4}>Source Document Selected</Title>
                    <Text size="md" c="dimmed">{sourceFile.name}</Text>
                    <Button variant="outline" size="xs" leftSection={<IconX size={14} />} onClick={handleClearSource}>
                      Clear document
                    </Button>
                  </Stack>
                )}

                <Stack gap="xs">
                  <Text size="sm" fw={500}>Or paste your source text</Text>
                  <Textarea
                    placeholder="Paste article content, notes, or an outline here..."
                    minRows={6}
                    autosize
                    value={sourceText}
                    onChange={(event) => setSourceText(event.currentTarget.value)}
                  />
                  {sourceText.trim().length > 0 && (
                    <Group justify="flex-end">
                      <Button variant="subtle" color="red" size="xs" leftSection={<IconX size={14} />} onClick={() => setSourceText('')}>
                        Clear text
                      </Button>
                    </Group>
                  )}
                  <Text size="xs" c="dimmed">
                    You can upload a document, paste text, or do both. The AI will use everything provided to build the outline.
                  </Text>
                </Stack>

                <NumberInput
                  label="Desired number of slides"
                  description="Tell the AI how many slides to plan for (1-30)."
                  min={1}
                  max={30}
                  value={slideCount}
                  onChange={(value) => setSlideCount(typeof value === 'number' ? value : DEFAULT_SLIDE_COUNT)}
                />
              </Stack>
            </Card>
          </Stepper.Step>

          <Stepper.Step label="Step 2" description="Generate Outline" icon={<IconBrain size={24} />}>
            <Card withBorder p="xl" radius="md" mt="xl">
              {outlineStatus === 'idle' && (
                <Text c="dimmed" ta="center">Click Next to generate a slide outline from your source material.</Text>
              )}

              {['uploading', 'pending'].includes(outlineStatus) && (
                <Stack align="center" gap="sm">
                  <Loader />
                  <Text c="dimmed">Generating outline...</Text>
                </Stack>
              )}

              {outlineStatus === 'ready' && (
                <Stack gap="md">
                  <Text size="sm" c="dimmed">Outline for {sourceFilename}</Text>
                  {outline.length > 0 ? (
                    outline.map((slide, index) => (
                      <Card withBorder key={`${slide.slide_title ?? 'slide'}-${index}`} radius="md" p="md">
                        <Stack gap="xs">
                          <Title order={5}>{`Slide ${index + 1}: ${slide.slide_title ?? 'Untitled'}`}</Title>
                          {Array.isArray(slide.bullet_outline) ? (
                            <Stack gap={4}>
                              {slide.bullet_outline.map((bullet, bulletIndex) => (
                                <Text size="sm" key={`bullet-${bulletIndex}`}>• {bullet}</Text>
                              ))}
                            </Stack>
                          ) : (
                            <Text size="sm" c="dimmed">No outline bullets provided.</Text>
                          )}
                        </Stack>
                      </Card>
                    ))
                  ) : (
                    <Text>No outline data returned.</Text>
                  )}
                  <Button variant="outline" size="xs" onClick={startOutlineGeneration}>
                    Regenerate Outline
                  </Button>
                </Stack>
              )}

              {outlineStatus === 'error' && (
                <Alert icon={<IconAlertCircle size="1rem" />} title="Outline failed" color="red" radius="md">
                  <Stack gap="sm">
                    <Text size="sm">We couldn&apos;t generate an outline. Please try again.</Text>
                    <Button size="xs" variant="outline" onClick={startOutlineGeneration}>Try again</Button>
                  </Stack>
                </Alert>
              )}
            </Card>
          </Stepper.Step>

          <Stepper.Step label="Step 3" description="Choose Image Strategy" icon={<IconPhoto size={24} />}>
            <Stack mt="xl" gap="lg">
              <Radio.Group
                value={imageStrategy}
                onChange={setImageStrategy}
                label="How should images be sourced for this presentation?"
                description="You can upload your own visuals, pull curated stock images, or let Gemini craft custom line art."
              >
                <Stack gap="sm">
                  <Radio value="uploaded" label="Upload my own images" description="Provide images manually and arrange them for each slide." />
                  <Radio value="unsplash" label="Use Unsplash images" description="Automatically pick high-quality stock photos that match the outline." />
                  <Radio value="gemini_line_art" label="Generate Gemini line art" description="Create monochrome illustrations tailored to each slide." />
                </Stack>
              </Radio.Group>

              {imageStrategy === 'uploaded' ? (
                <Stack gap="md">
                  <FileDropzone
                    onDrop={(newFiles) => setImageFiles((current) => [...current, ...newFiles])}
                    fileType="image"
                    title="Drag & drop images"
                    subtitle="or click to add more images"
                  />
                  {imageFiles.length > 0 && (
                    <Stack>
                      <Text size="sm" fw={500}>Arrange your images in the order they should appear in the presentation:</Text>
                      <SortableImageList files={imageFiles} setFiles={setImageFiles} />
                      <Button variant="outline" color="red" size="xs" leftSection={<IconX size={14} />} onClick={() => setImageFiles([])}>
                        Clear all images
                      </Button>
                    </Stack>
                  )}
                </Stack>
              ) : (
                <Alert color="blue" variant="light" title="No upload required">
                  Images will be generated automatically once you continue.
                </Alert>
              )}
            </Stack>
          </Stepper.Step>

          <Stepper.Step label="Step 4" description="Generate Plan" icon={<IconSparkles size={24} />}>
            <Center mt="xl" p="xl">
              <Stack align="center" gap="sm">
                <Title order={3}>Ready to Generate!</Title>
                <Text c="dimmed" ta="center">
                  {imageStrategy === 'uploaded'
                    ? 'The AI will now analyze your outline and uploaded images to create a slide plan.'
                    : 'The AI will use your outline and automatically sourced visuals to create a slide plan.'}
                </Text>
                <Button size="lg" onClick={handleGeneratePlan} loading={status === 'generating'}>
                  Generate AI Plan
                </Button>
              </Stack>
            </Center>
          </Stepper.Step>
        </Stepper>

        <Group justify="center" mt="xl">
          {activeStep > 0 && <Button variant="default" onClick={handleBack}>Back</Button>}
          {activeStep < 3 && (
            <Button onClick={handleNext} disabled={isNextDisabled()}>
              Next
            </Button>
          )}
        </Group>

        {error && <Alert icon={<IconAlertCircle size="1rem" />} title="Error!" color="red" mt="lg" withCloseButton onClose={() => setError('')}>{error}</Alert>}
      </Stack>
    </Container>
  );
}
