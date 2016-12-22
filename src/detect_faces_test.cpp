#include "opencv2/objdetect/objdetect.hpp"
#include "opencv2/highgui/highgui.hpp"
#include "opencv2/imgproc/imgproc.hpp"
 
#include <iostream>
#include <stdio.h>
 
using namespace std;
using namespace cv;
 
Mat detectFace(Mat src);
 
int main( )
{
 VideoCapture cap(0);
 cap.set(CV_CAP_PROP_FRAME_WIDTH, 640);
 cap.set(CV_CAP_PROP_FRAME_HEIGHT, 480);
 namedWindow( "window1", 1 );   
 
 while(1)
 {
  Mat frame;
  cap >> frame;         
  frame=detectFace(frame);
   
  imshow( "window1", frame );
  // Press 'c' to escape
  if(waitKey(1) == 'c') break;  
 }
 
 waitKey(0);                  
 return 0;
}
 
Mat detectFace(Mat image)
{
 // Load Face cascade (.xml file)
 CascadeClassifier face_cascade;
 if (!face_cascade.load(FACE_CASCADE_FILE)) {
    std::cout << "Unable to load face cascade file\n";
    exit(1);
 }
 
 // Detect faces
 std::vector<Rect> faces;
 face_cascade.detectMultiScale( image, faces, 1.1, 3, 0|CV_HAAR_SCALE_IMAGE, Size(100, 100) );
 
 // Draw circles on the detected faces
 for( int i = 0; i < faces.size(); i++ )
 {
  Point center( faces[i].x + faces[i].width*0.5, faces[i].y + faces[i].height*0.5 );
  ellipse( image, center, Size( faces[i].width*0.5, faces[i].height*0.5), 0, 0, 360, Scalar( 255, 0, 255 ), 4, 8, 0 );
 } 
 return image;
}