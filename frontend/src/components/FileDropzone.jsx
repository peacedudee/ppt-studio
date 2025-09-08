import { Group, Text, rem } from '@mantine/core';
import { IconUpload, IconPhoto, IconX } from '@tabler/icons-react';
import { Dropzone, IMAGE_MIME_TYPE, MIME_TYPES } from '@mantine/dropzone';
import classes from './FileDropzone.module.css';

// Add title and subtitle props
export function FileDropzone({ onDrop, fileType = 'any', multiple = true, title, subtitle }) {
  const getAcceptTypes = () => {
    if (fileType === 'ppt') {
      return [MIME_TYPES.pptx];
    }
    if (fileType === 'image') {
      return IMAGE_MIME_TYPE;
    }
    return [];
  };

  return (
    <Dropzone
      onDrop={onDrop}
      maxSize={30 * 1024 ** 2}
      accept={getAcceptTypes()}
      multiple={multiple}
      className={classes.dropzone}
    >
      <Group justify="center" gap="xl" mih={150} style={{ pointerEvents: 'none' }}>
        <Dropzone.Accept>
          <IconUpload style={{ width: rem(52), height: rem(52), color: 'var(--mantine-color-blue-6)' }} stroke={1.5} />
        </Dropzone.Accept>
        <Dropzone.Reject>
          <IconX style={{ width: rem(52), height: rem(52), color: 'var(--mantine-color-red-6)' }} stroke={1.5} />
        </Dropzone.Reject>
        <Dropzone.Idle>
          <IconPhoto style={{ width: rem(52), height: rem(52), color: 'var(--mantine-color-dimmed)' }} stroke={1.5} />
        </Dropzone.Idle>

        <div>
          {/* Use the new props for dynamic text */}
          <Text size="xl" inline>
            {title || 'Drag files here or click to select'}
          </Text>
          <Text size="sm" c="dimmed" inline mt={7}>
            {subtitle || 'Attach files as you like'}
          </Text>
        </div>
      </Group>
    </Dropzone>
  );
}