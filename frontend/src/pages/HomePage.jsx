import { Title, Text, Container, SimpleGrid, Card, Button, Group, Stack, List, ThemeIcon } from '@mantine/core';
import { IconWand, IconFilePlus } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import classes from './HomePage.module.css';

// Add a 'details' array to each feature
const features = [
  {
    icon: IconWand,
    title: 'PPT Enhancer',
    description: 'For existing presentations that need a professional touch. Upload your file and let our AI do the heavy lifting.',
    details: [
        'Dynamically add your company logo.',
        'Append standardized, hyperlinked credits.',
        'Generate insightful speaker notes for every slide.',
        'Automatically clean and remove watermarks.'
    ],
    link: '/enhancer',
    buttonText: 'Enhance a Presentation'
  },
  {
    icon: IconFilePlus,
    title: 'PPT Creator',
    description: 'For when you need to build a new presentation from scratch. Provide the content, and we provide the structure.',
    details: [
        'Converts documents (PDF, DOCX) into slide plans.',
        'AI structures your content into titles and bullets.',
        'Review and edit the AI-generated plan.',
        'Builds a final .pptx with intelligent layouts.'
    ],
    link: '/creator',
    buttonText: 'Create a New Presentation'
  },
];

export default function HomePage() {
  const items = features.map((feature) => (
    <Card key={feature.title} className={classes.card} padding="xl" radius="md">
      <Stack justify="space-between" style={{ height: '100%' }}>
        <div>
          <Group>
            <ThemeIcon variant="light" size={50} radius="md">
              <feature.icon style={{ width: '60%', height: '60%' }} />
            </ThemeIcon>
            <Title order={3}>{feature.title}</Title>
          </Group>
          <Text c="dimmed" mt="md">
            {feature.description}
          </Text>
          {/* Map over the new details array to create a list */}
          <List size="sm" mt="md" spacing="xs">
            {feature.details.map((detail, index) => (
                <List.Item key={index}>{detail}</List.Item>
            ))}
          </List>
        </div>
        <Button component={Link} to={feature.link} fullWidth mt="xl" size="md" variant="outline">
          {feature.buttonText}
        </Button>
      </Stack>
    </Card>
  ));

  return (
    <Container className={classes.hero}>
      <Stack align="center" gap="md">
        <Title order={1} ta="center" className={classes.title}>
          Automate Your Presentations
        </Title>
        <Text c="dimmed" ta="center" size="lg" maw={600}>
          A modern toolkit to create and enhance your slide decks. Save time and focus on your message.
        </Text>
        <Group mt="md">
            <Button component={Link} to="/creator" size="lg" variant="gradient" gradient={{ from: 'cyan', to: 'blue' }}>Get Started</Button>
            <Button component={Link} to="/enhancer" size="lg" variant="default">Enhance Existing PPT</Button>
        </Group>
      </Stack>
      
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xl" mt={50}>
        {items}
      </SimpleGrid>
    </Container>
  );
}