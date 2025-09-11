import { useState, useEffect } from 'react';
import { enhancePresentation, getJobStatus, API_BASE_URL } from '../services/api';
import { Container, Stack, Title, Text, Alert, Loader, Group, Button, TextInput, Stepper, Center, FileInput, Card } from '@mantine/core';
import { IconCircleCheck, IconFileUpload, IconPhoto, IconTag, IconSparkles, IconAlertCircle, IconX } from '@tabler/icons-react';
import { FileDropzone } from '../components/FileDropzone';

export default function EnhancerPage() {
  const [activeStep, setActiveStep] = useState(0);
  const [pptFile, setPptFile] = useState(null);
  const [logoFile, setLogoFile] = useState(null);
  const [creditsText, setCreditsText] = useState('');
  
  const [status, setStatus] = useState('idle');
  const [jobId, setJobId] = useState(null);
  const [jobResult, setJobResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (status !== 'processing' || !jobId) return;
    
    const intervalId = setInterval(async () => {
      try {
        const statusResult = await getJobStatus(jobId);
        if (statusResult.status === 'SUCCESS') {
          clearInterval(intervalId);
          setStatus('complete');
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
  }, [status, jobId]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!pptFile) {
      setError('Please select a presentation file.');
      return;
    }
    setStatus('processing');
    setError('');
    try {
      const result = await enhancePresentation(pptFile, logoFile, creditsText);
      setJobResult(result);
      setJobId(result.job_id);
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const handleDownload = () => {
    if (!jobResult) return;
    // The backend now provides a redirect to a secure GCS URL
    window.location.href = `${API_BASE_URL}/api/v1/enhancer/download/${jobResult.job_id}/${jobResult.output_filename}`;
  };
  
  const handleReset = () => {
    setPptFile(null);
    setLogoFile(null);
    setCreditsText('');
    setStatus('idle');
    setJobId(null);
    setJobResult(null);
    setError('');
    setActiveStep(0);
  };
  
  const nextStep = () => setActiveStep((current) => (current < 3 ? current + 1 : current));
  const prevStep = () => setActiveStep((current) => (current > 0 ? current - 1 : current));

  if (status === 'processing') {
    return (
      <Container size="sm" mt="xl">
        <Stack align="center" gap="lg">
            <Loader size="lg" />
            <Title order={3}>Enhancing Your Presentation</Title>
            <Text c="dimmed">This can take up to a minute, please wait...</Text>
        </Stack>
      </Container>
    );
  }

  if (status === 'complete') {
    return (
       <Container size="sm" mt="xl">
        <Alert icon={<IconCircleCheck size="1.2rem" />} title="Success!" color="teal" variant="light" radius="md">
            <Stack>
              <Text>Your presentation has been enhanced and is ready for download.</Text>
              <Button onClick={handleDownload} size="md">
                Download File
              </Button>
              <Button variant="default" onClick={handleReset}>
                Enhance Another Presentation
              </Button>
            </Stack>
          </Alert>
      </Container>
    );
  }

  return (
    <Container size="md">
        <Stack gap="xl" align="center">
            <Stack gap="xs" align="center" mt="md">
                <Title order={1}>PPT Enhancer</Title>
                <Text c="dimmed" ta="center" size="lg">Follow the steps to add a logo, custom credits, and AI speaker notes to your presentation.</Text>
            </Stack>

            <Stepper active={activeStep} onStepClick={setActiveStep} allowNextStepsSelect={false} style={{ width: '100%' }} mt="lg">
                <Stepper.Step label="Step 1" description="Upload Presentation" icon={<IconFileUpload size={24} />}>
                    <Card withBorder p="xl" radius="md" mt="xl">
                        {!pptFile ? (
                            <FileDropzone 
                                onDrop={(files) => setPptFile(files[0])} 
                                multiple={false}
                                fileType="ppt"
                                title="Drag & drop presentation"
                                subtitle="or click to select a single .pptx file"
                            />
                        ) : (
                            <Stack align="center">
                                <IconCircleCheck size={48} color="var(--mantine-color-teal-5)" />
                                <Title order={4}>File Selected</Title>
                                <Text size="md" c="dimmed">{pptFile.name}</Text>
                                <Button variant="outline" size="xs" leftSection={<IconX size={14} />} onClick={() => setPptFile(null)}>
                                    Clear selection
                                </Button>
                            </Stack>
                        )}
                    </Card>
                </Stepper.Step>
                <Stepper.Step label="Step 2" description="Add Branding" icon={<IconPhoto size={24} />}>
                    <Stack mt="xl">
                        <FileInput
                            label="Custom Logo (Optional)"
                            placeholder="Select a logo image"
                            value={logoFile}
                            onChange={setLogoFile}
                            accept="image/*"
                            size="md"
                        />
                        <TextInput
                            label="Custom Credits Text (Optional)"
                            placeholder="e.g., Presented by MyCompany"
                            value={creditsText}
                            onChange={(e) => setCreditsText(e.target.value)}
                            size="md"
                            leftSection={<IconTag size={18} />}
                        />
                    </Stack>
                </Stepper.Step>
                <Stepper.Step label="Step 3" description="Enhance" icon={<IconSparkles size={24} />}>
                    <Center mt="xl" p="xl">
                       <Stack align="center">
                         <Title order={3}>Ready to Go!</Title>
                         <Text c="dimmed" ta="center">Click the button below to start the enhancement process.</Text>
                         {pptFile && <Text size="sm">Presentation: <strong>{pptFile.name}</strong></Text>}
                         {logoFile && <Text size="sm">Logo: <strong>{logoFile.name}</strong></Text>}
                         {creditsText && <Text size="sm">Credits: <strong>{creditsText}</strong></Text>}
                       </Stack>
                    </Center>
                </Stepper.Step>
            </Stepper>
            
            <Group justify="center" mt="xl">
                {activeStep > 0 && <Button variant="default" onClick={prevStep}>Back</Button>}
                {activeStep < 2 && <Button onClick={nextStep} disabled={!pptFile}>Next</Button>}
                {activeStep === 2 && <Button size="lg" onClick={handleSubmit}>Enhance Presentation</Button>}
            </Group>

            {status === 'error' && (
                <Alert icon={<IconAlertCircle size="1rem" />} title="Error!" color="red" mt="lg" withCloseButton onClose={() => setError('')}>
                    {error}
                </Alert>
            )}
        </Stack>
    </Container>
  );
}