import { useState, useEffect } from 'react';
import { generateSlidePlan, buildPresentation, getJobStatus, API_BASE_URL } from '../services/api';
import SlideEditor from '../components/SlideEditor';
import { Container, Title, Text, Button, Group, Loader, Alert, SimpleGrid, Stack, Stepper, Center, Card } from '@mantine/core';
import { IconCircleCheck, IconAlertCircle, IconFileTypePdf, IconPhoto, IconBrain, IconX } from '@tabler/icons-react';
import { FileDropzone } from '../components/FileDropzone';
import SortableImageList from '../components/SortableImageList';

export default function CreatorPage() {
  const [activeStep, setActiveStep] = useState(0);
  const [sourceFile, setSourceFile] = useState(null);
  const [imageFiles, setImageFiles] = useState([]);
  
  const [planJobId, setPlanJobId] = useState('');
  const [buildJobId, setBuildJobId] = useState('');
  const [slidePlan, setSlidePlan] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [finalUrl, setFinalUrl] = useState('');

  useEffect(() => {
    if (status !== 'generating' && status !== 'building') return;
    
    const currentJobId = status === 'generating' ? planJobId : buildJobId;
    if (!currentJobId) return;

    const intervalId = setInterval(async () => {
      try {
        const statusResult = await getJobStatus(currentJobId);
        if (statusResult.status === 'SUCCESS') {
          clearInterval(intervalId);
          if (status === 'generating') {
            setSlidePlan(statusResult.result.slide_plan); 
            setStatus('review');
          } else {
            const downloadUrl = `${API_BASE_URL}/api/v1/creator/download/${planJobId}`;
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
  }, [status, planJobId, buildJobId]);

  const handleGeneratePlan = async () => {
    if (!sourceFile || imageFiles.length === 0) {
      setError('Please upload a source document and at least one image.');
      return;
    }
    setStatus('generating');
    setError('');
    try {
      const allFiles = [sourceFile, ...imageFiles];
      const result = await generateSlidePlan(allFiles);
      setPlanJobId(result.job_id);
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };
  
  const handleBuildPresentation = async () => {
    setStatus('building');
    try {
      const result = await buildPresentation(planJobId, slidePlan);
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
    setSourceFile(null);
    setImageFiles([]);
    setPlanJobId('');
    setBuildJobId('');
    setSlidePlan(null);
    setStatus('idle');
    setError('');
    setFinalUrl('');
    setActiveStep(0);
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

        <Stepper active={activeStep} onStepClick={setActiveStep} allowNextStepsSelect={false} style={{ width: '100%' }} mt="lg">
          <Stepper.Step label="Step 1" description="Upload Source Document" icon={<IconFileTypePdf size={24} />}>
            <Card withBorder p="xl" radius="md" mt="xl">
              {!sourceFile ? (
                <FileDropzone 
                  onDrop={(files) => setSourceFile(files[0])} 
                  multiple={false}
                  fileType="doc"
                  title="Drag & drop source document"
                  subtitle="or click to select a PDF, DOCX, or TXT file"
                />
              ) : (
                <Stack align="center">
                  <IconCircleCheck size={48} color="var(--mantine-color-teal-5)" />
                  <Title order={4}>Source Document Selected</Title>
                  <Text size="md" c="dimmed">{sourceFile.name}</Text>
                  <Button variant="outline" size="xs" leftSection={<IconX size={14} />} onClick={() => setSourceFile(null)}>
                    Clear selection
                  </Button>
                </Stack>
              )}
            </Card>
          </Stepper.Step>

          <Stepper.Step label="Step 2" description="Upload & Order Images" icon={<IconPhoto size={24} />}>
            <Stack mt="xl">
              <FileDropzone 
                onDrop={(newFiles) => setImageFiles((current) => [...current, ...newFiles])}
                fileType="image"
                title="Drag & drop images"
                subtitle="or click to add more images"
              />
              {imageFiles.length > 0 && (
                <Stack mt="md">
                  <Text size="sm" fw={500}>Arrange your images in the order they should appear in the presentation:</Text>
                  <SortableImageList files={imageFiles} setFiles={setImageFiles} />
                  <Button variant="outline" color="red" size="xs" leftSection={<IconX size={14} />} onClick={() => setImageFiles([])}>
                    Clear all images
                  </Button>
                </Stack>
              )}
            </Stack>
          </Stepper.Step>

          <Stepper.Step label="Step 3" description="Generate Plan" icon={<IconBrain size={24} />}>
            <Center mt="xl" p="xl">
                <Stack align="center">
                  <Title order={3}>Ready to Generate!</Title>
                  <Text c="dimmed" ta="center">The AI will now analyze your content and images to create a slide plan.</Text>
                  <Button size="lg" onClick={handleGeneratePlan} loading={status === 'generating'}>
                    Generate AI Plan
                  </Button>
                </Stack>
            </Center>
          </Stepper.Step>
        </Stepper>
            
        <Group justify="center" mt="xl">
            {activeStep > 0 && <Button variant="default" onClick={() => setActiveStep(activeStep - 1)}>Back</Button>}
            {activeStep < 2 && <Button onClick={() => setActiveStep(activeStep + 1)} disabled={(activeStep === 0 && !sourceFile) || (activeStep === 1 && imageFiles.length === 0)}>Next</Button>}
        </Group>

        {error && <Alert icon={<IconAlertCircle size="1rem" />} title="Error!" color="red" mt="lg" withCloseButton onClose={() => setError('')}>{error}</Alert>}
      </Stack>
    </Container>
  );
}