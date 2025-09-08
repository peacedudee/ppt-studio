import { useState } from 'react';
import { Container, Title, Text, TextInput, Textarea, Select, Button, Stack, Alert, SimpleGrid } from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconCircleCheck } from '@tabler/icons-react';
import { submitFeedback } from '../services/api';

export default function FeedbackPage() {
  const [status, setStatus] = useState('idle'); // idle, sending, success, error

  const form = useForm({
    initialValues: {
      name: '',
      email: '',
      feedback_type: 'General Comment',
      message: '',
    },
    validate: {
      message: (value) => (value.trim().length < 10 ? 'Feedback message must be at least 10 characters long' : null),
      email: (value) => (value && !/^\S+@\S+$/.test(value) ? 'Invalid email address' : null),
    },
  });

  const handleSubmit = async (values) => {
    setStatus('sending');
    try {
      await submitFeedback(values);
      setStatus('success');
    } catch (error) {
      setStatus('error');
    }
  };

  if (status === 'success') {
    return (
      <Container size="sm" mt="xl">
        <Alert icon={<IconCircleCheck size="1.2rem" />} title="Thank You!" color="teal" variant="light" radius="md">
          <Text>Your feedback has been submitted successfully. We appreciate you taking the time to help us improve!</Text>
        </Alert>
      </Container>
    );
  }

  return (
    <Container size="sm">
      <Stack gap="lg">
        <Stack gap="xs" align="center" mt="md">
          <Title order={1}>Submit Feedback</Title>
          <Text c="dimmed" ta="center">We'd love to hear your thoughts. Let us know what we're doing well or where we can improve.</Text>
        </Stack>

        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <TextInput label="Name (Optional)" placeholder="Your name" {...form.getInputProps('name')} />
              <TextInput label="Email (Optional)" placeholder="your@email.com" {...form.getInputProps('email')} />
            </SimpleGrid>
            <Select
              label="Feedback Type"
              data={['General Comment', 'Bug Report', 'Feature Request']}
              {...form.getInputProps('feedback_type')}
              required
            />
            <Textarea
              label="Message"
              placeholder="Your feedback..."
              withAsterisk
              minRows={5}
              {...form.getInputProps('message')}
            />
            <Button type="submit" loading={status === 'sending'} size="md" mt="md">
              Submit Feedback
            </Button>
            {status === 'error' && <Text c="red" size="sm" ta="center" mt="xs">Could not submit feedback. Please try again later.</Text>}
          </Stack>
        </form>
      </Stack>
    </Container>
  );
}