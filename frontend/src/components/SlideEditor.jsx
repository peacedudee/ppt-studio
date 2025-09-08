import { Card, TextInput, Textarea, Stack, Title, Image } from '@mantine/core';

export default function SlideEditor({ slide, index, imageUrl, onUpdate }) {
  const handleInputChange = (field, value) => {
    onUpdate(index, { ...slide, [field]: value });
  };

  const handleContentChange = (event) => {
    const newContent = event.currentTarget.value.split('\n');
    onUpdate(index, { ...slide, slide_content: newContent });
  };

  return (
    <Card withBorder shadow="sm" radius="md">
      <Stack>
        <Title order={5}>Slide {index + 1}</Title>
        
        {imageUrl && (
          <Card.Section>
            <Image
              src={imageUrl}
              height={180}
              alt={`Preview for slide ${index + 1}`}
              fit="contain"
              style={{ backgroundColor: 'var(--mantine-color-dark-5)' }}
            />
          </Card.Section>
        )}
        
        <TextInput
          label="Slide Title"
          value={slide.slide_title}
          onChange={(e) => handleInputChange('slide_title', e.target.value)}
        />
        <Textarea
          label="Bullet Points (one per line)"
          value={slide.slide_content.join('\n')}
          onChange={handleContentChange}
          autosize
          minRows={3}
        />
        <Textarea
          label="Speaker Notes"
          value={slide.speaker_notes}
          onChange={(e) => handleInputChange('speaker_notes', e.target.value)}
          autosize
          minRows={2}
          c="dimmed"
        />
      </Stack>
    </Card>
  );
}